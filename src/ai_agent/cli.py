"""CLI entrypoints for console, WebSocket, ingest, and multi-agent modes."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_agent.application.agent import Agent
from ai_agent.domain.ports import Retriever
from ai_agent.infrastructure.chroma_retriever import (
    ChromaRetriever,
    InMemoryRetriever,
    load_docs_folder,
)
from ai_agent.infrastructure.config_loader import ConfigError, load_agent_config
from ai_agent.infrastructure.embedder import OpenRouterEmbedder
from ai_agent.infrastructure.llm import OpenRouterLLM
from ai_agent.infrastructure.server import WebSocketServer
from ai_agent.infrastructure.sqlite_store import SqliteStore
from ai_agent.orchestration.runtime import AgentRuntime
from ai_agent.tools import build_default_registry

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    """
    Log to stderr so aioconsole's non-blocking stdout does not raise BlockingIOError.
    Keep noisy HTTP libraries quieter even with -v.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def _build_retriever(chroma_path: str) -> Retriever:
    embedder = OpenRouterEmbedder()
    try:
        return ChromaRetriever(chroma_path, embedder)
    except ImportError:
        logger.warning("chromadb not installed; using in-memory retriever")
        return InMemoryRetriever(embedder)


def build_agent(
    config_path: Path,
    agent_id: str = "agent",
    *,
    messenger: AgentRuntime | None = None,
    sender_id: str | None = None,
) -> Agent:
    """Composition root: wire config, tools, and LLM into an Agent."""
    config = load_agent_config(config_path)
    store = SqliteStore(config.sqlite_path)
    retriever = _build_retriever(config.chroma_path)

    registry = build_default_registry(
        workspace_root=config.workspace_root,
        memory_store=store,
        retriever=retriever,
        messenger=messenger,
        messenger_sender_id=sender_id or agent_id,
    )
    selected = registry.select(config.tools) if config.tools else registry
    llm = OpenRouterLLM(model=config.model)
    return Agent(config=config, llm=llm, registry=selected, agent_id=agent_id)


async def _run_console(config_path: Path) -> None:
    agent = build_agent(config_path)
    await agent.run()


async def _run_server(config_path: Path, host: str, port: int) -> None:
    config = load_agent_config(config_path)
    store = SqliteStore(config.sqlite_path)

    def factory(agent_id: str) -> Agent:
        return build_agent(config_path, agent_id=agent_id)

    server = WebSocketServer(factory, host=host, port=port, session_store=store)
    await server.serve()


async def _run_multi_agent(
    coordinator_config: Path,
    researcher_config: Path,
) -> None:
    """Console UX against the coordinator; researcher runs in the background."""
    from aioconsole import ainput

    turn_done = asyncio.Event()

    def on_output(agent_id: str, result: object) -> None:
        message = getattr(result, "message", str(result))
        if agent_id == "coordinator":
            print(f"Assistant: {message}", flush=True)
            turn_done.set()
        else:
            logger.info("[%s] %s", agent_id, message)

    coord_cfg = load_agent_config(coordinator_config)
    store = SqliteStore(coord_cfg.sqlite_path)
    runtime = AgentRuntime(on_agent_output=on_output, session_store=store)

    researcher = build_agent(researcher_config, agent_id="researcher")
    coordinator = build_agent(
        coordinator_config,
        agent_id="coordinator",
        messenger=runtime,
        sender_id="coordinator",
    )

    runtime.register("researcher", researcher)
    runtime.register("coordinator", coordinator)
    await runtime.start_agent("researcher")
    await runtime.start_agent("coordinator")
    await asyncio.sleep(0.05)

    # Fresh agents publish a greeting; resumed (non-done) sessions skip it.
    if runtime.get_session("coordinator").messages and not turn_done.is_set():
        print("Assistant: (session resumed — continue chatting)", flush=True)
        turn_done.set()
    else:
        await asyncio.wait_for(turn_done.wait(), timeout=30.0)

    try:
        while runtime._contexts["coordinator"].active:  # noqa: SLF001
            if runtime.get_session("coordinator").done:
                break
            user_input = await ainput("You: ")
            text = user_input.strip()
            if not text:
                continue
            if text.lower() in {"exit", "quit", "bye"}:
                break
            turn_done.clear()
            await runtime.send_message("coordinator", text)
            await asyncio.wait_for(turn_done.wait(), timeout=180.0)
    except TimeoutError:
        print("Timed out waiting for the coordinator.", file=sys.stderr)
    finally:
        await runtime.shutdown()


async def _run_ingest(docs_dir: Path, chroma_path: str) -> None:
    documents = load_docs_folder(docs_dir)
    if not documents:
        raise ValueError(f"No documents found under {docs_dir}")
    embedder = OpenRouterEmbedder()
    try:
        retriever = ChromaRetriever(chroma_path, embedder)
    except ImportError as exc:
        raise SystemExit(
            "chromadb is required for ingest. Install with: pip install 'ai-agent[rag]'"
        ) from exc
    count = await retriever.ingest(documents)
    print(f"Ingested {count} chunks from {docs_dir} into {chroma_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-agent",
        description="Generic tool-using conversational agent",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config/agent_config.yaml"),
        help="Path to agent YAML config",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run as a WebSocket server instead of console",
    )
    parser.add_argument(
        "--multi-agent",
        action="store_true",
        help="Run coordinator + researcher multi-agent console demo",
    )
    parser.add_argument(
        "--coordinator-config",
        type=Path,
        default=Path("config/agents/coordinator.yaml"),
        help="Coordinator YAML for --multi-agent",
    )
    parser.add_argument(
        "--researcher-config",
        type=Path,
        default=Path("config/agents/researcher.yaml"),
        help="Researcher YAML for --multi-agent",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["ingest"],
        help="Optional subcommand (ingest)",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=Path("docs"),
        help="Docs directory for ingest",
    )
    parser.add_argument(
        "--chroma-path",
        default=".ai_agent/chroma",
        help="Chroma persistence path for ingest",
    )
    parser.add_argument("--host", default="localhost", help="WebSocket host")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    try:
        if args.command == "ingest":
            asyncio.run(_run_ingest(args.docs, args.chroma_path))
        elif args.multi_agent:
            asyncio.run(_run_multi_agent(args.coordinator_config, args.researcher_config))
        elif args.server:
            asyncio.run(_run_server(args.config, args.host, args.port))
        else:
            asyncio.run(_run_console(args.config))
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
