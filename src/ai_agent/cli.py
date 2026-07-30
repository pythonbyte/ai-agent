"""CLI entrypoints for console and WebSocket modes."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_agent.application.agent import Agent
from ai_agent.infrastructure.config_loader import ConfigError, load_agent_config
from ai_agent.infrastructure.llm import OpenRouterLLM
from ai_agent.infrastructure.server import WebSocketServer
from ai_agent.tools import build_default_registry


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def build_agent(config_path: Path, agent_id: str = "agent") -> Agent:
    """Composition root: wire config, tools, and LLM into an Agent."""
    config = load_agent_config(config_path)
    full_registry = build_default_registry()
    registry = full_registry.select(config.tools) if config.tools else full_registry
    llm = OpenRouterLLM(model=config.model)
    return Agent(config=config, llm=llm, registry=registry, agent_id=agent_id)


async def _run_console(config_path: Path) -> None:
    agent = build_agent(config_path)
    await agent.run()


async def _run_server(config_path: Path, host: str, port: int) -> None:
    def factory(agent_id: str) -> Agent:
        return build_agent(config_path, agent_id=agent_id)

    server = WebSocketServer(factory, host=host, port=port)
    await server.serve()


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
    parser.add_argument("--host", default="localhost", help="WebSocket host")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    try:
        if args.server:
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
