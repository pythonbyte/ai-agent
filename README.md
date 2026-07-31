# ai-agent

**A typed agent harness for tool-using LLMs.**

> **Agent = Model + Harness**  
> The model reasons. This repository is the harness: the loop, tools, memory, retrieval, guardrails, and multi-agent runtime that turn a chat completion into a reliable agent.

Built with Clean Architecture, strict typing (`mypy`), and a test suite that includes **mutation testing** (`mutmut`) — designed as both a production starting point and a hireable reference codebase.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-0B7285)](LICENSE)
[![Typed](https://img.shields.io/badge/typing-mypy%20strict-2F9E44)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-pytest%20%2B%20mutmut-7048E8)](tests/)
[![uv](https://img.shields.io/badge/packaging-uv-DE5FE9?logo=uv)](https://github.com/astral-sh/uv)

---

## Why this exists

Most “agent demos” hide the interesting part inside a framework black box. This kit makes the harness **explicit and readable**:

| Goal | How this repo delivers |
|---|---|
| Learn / teach agent internals | ReAct loop, tool registry, and ports are first-class modules — not magic |
| Ship a real assistant | YAML config, pluggable tools, SQLite memory, DuckDuckGo search, optional Chroma RAG |
| Stay maintainable | Domain → Application → Infrastructure, DI via protocols, no SDK lock-in |
| Prove quality | `pytest` + `mypy` + `ruff` + `mutmut` on safety-critical paths |

---

## Agent harness capabilities

Everything below is **deterministic software around the model** (OpenRouter today — swap via `LLMPort`).

| Capability | Status | What you get | Where it lives |
|---|---|---|---|
| **Decide → act → observe loop** | Done | Bounded ReAct loop (`respond` / `call_tools` / `done`) with `max_tool_rounds` | [`application/loop.py`](src/ai_agent/application/loop.py) |
| **Structured decisions** | Done | Pydantic `AgentDecision`; coerces tool-name-as-kind mistakes from LLMs | [`domain/models.py`](src/ai_agent/domain/models.py) |
| **Tool registry & dispatch** | Done | Name → tool map, config `select()`, safe `execute()` | [`application/registry.py`](src/ai_agent/application/registry.py) |
| **Argument validation** | Done | Required / type / unknown-key checks before any tool I/O | [`application/tool_args.py`](src/ai_agent/application/tool_args.py) |
| **Web tools** | Done | `web_search` (DuckDuckGo) + `http_get` (http/https only, size limits) | [`tools/`](src/ai_agent/tools/) · [`infrastructure/`](src/ai_agent/infrastructure/) |
| **Workspace tools** | Done | Sandboxed `workspace_search` / read under `workspace_root` | [`infrastructure/workspace_fs.py`](src/ai_agent/infrastructure/workspace_fs.py) |
| **Session state** | Done | Per-conversation messages + tool traces; finished sessions restart cleanly | [`domain/state.py`](src/ai_agent/domain/state.py) · [`orchestration/runtime.py`](src/ai_agent/orchestration/runtime.py) |
| **Durable memory** | Done | SQLite KV `memory` tool + session persistence | [`infrastructure/sqlite_store.py`](src/ai_agent/infrastructure/sqlite_store.py) |
| **RAG as a tool** | Done | Local Chroma (+ in-memory tests); `ai-agent ingest --docs` | [`infrastructure/chroma_retriever.py`](src/ai_agent/infrastructure/chroma_retriever.py) |
| **Multi-agent handoff** | Done | Coordinator → `message_agent` → researcher (sync ask + timeout) | [`orchestration/runtime.py`](src/ai_agent/orchestration/runtime.py) · [`config/agents/`](config/agents/) |
| **Serving surfaces** | Done | Console CLI, WebSocket chat (`--server`), multi-agent demo | [`cli.py`](src/ai_agent/cli.py) · [`infrastructure/server.py`](src/ai_agent/infrastructure/server.py) |
| **Guardrails (light)** | Done | URL scheme allowlist, path jail, AST calculator, typed config | `url_safety` · `workspace_fs` · `calculator` |
| **Provider portability** | Done | `LLMPort` + httpx OpenRouter adapter (no SDK lock-in) | [`infrastructure/llm.py`](src/ai_agent/infrastructure/llm.py) |
| **Context compaction** | — | Full history in window today | Roadmap |
| **HITL approvals** | — | No human-in-the-loop gates yet | Roadmap |
| **OS / container sandbox** | — | Scoped limits only (not Docker/Firecracker) | Roadmap |

**Model (not harness):** whatever you set in YAML (`openai/gpt-4o-mini`, etc.) via OpenRouter.

---

## Architecture

```text
src/ai_agent/
├── domain/           # models, ConversationState, Tool protocol, ports
├── application/      # Agent, ReAct loop, ToolRegistry, arg / URL validation
├── infrastructure/   # OpenRouter, SQLite, Chroma, DuckDuckGo, FS, WebSocket
├── orchestration/    # multi-agent runtime (inbox / outbox / ask)
├── tools/            # thin adapters over ports
└── cli.py            # composition root
```

```text
                  ┌─────────────────────────────────────────┐
  User / WS  ───► │  AgentRuntime (orchestration)           │
                  │    inbox → Agent.step → outbox          │
                  └───────────────┬─────────────────────────┘
                                  │
                  ┌───────────────▼─────────────────────────┐
                  │  Harness loop (application)             │
                  │  decide → ToolRegistry → observe        │
                  └───────┬─────────────────────┬───────────┘
                          │                     │
                 LLMPort (model)         tools → ports → infra
                 OpenRouter              search / FS / memory / RAG
```

Dependency rule: **inward only**. The loop depends on protocols, never on httpx/Chroma/SQLite directly. See [DECISIONS.md](DECISIONS.md).

---

## Quick start

**Requirements:** Python 3.12+, an [OpenRouter](https://openrouter.ai/) API key.

```bash
git clone https://github.com/pythonbyte/ai-agent.git
cd ai-agent

uv sync --all-extras
cp .env.example .env   # OPENROUTER_API_KEY=...

uv run ai-agent -c config/agent_config.yaml
```

With pip:

```bash
pip install -e ".[dev,rag]"
ai-agent -c config/agent_config.yaml
```

### Modes

| Mode | Command | Notes |
|---|---|---|
| Console | `uv run ai-agent -c config/agent_config.yaml` | Single agent |
| WebSocket | `uv run ai-agent --server -v` then `websocat ws://localhost:8765` | Chat-style plain text replies |
| Multi-agent | `uv run ai-agent --multi-agent -v` | Coordinator + researcher handoff |
| RAG ingest | `uv run ai-agent ingest --docs docs/` | Needs `[rag]` extra |

---

## Built-in tools

| Tool | Purpose |
|---|---|
| `web_search` | DuckDuckGo search (titles, URLs, snippets) |
| `http_get` | Fetch http(s) page text (timeout + size cap) |
| `workspace_search` | Search / read files under `workspace_root` |
| `retrieve` | Semantic search over ingested docs (Chroma) |
| `memory` | Durable key/value facts (SQLite) |
| `calculator` | Safe AST arithmetic |
| `current_time` | Clock / timezone |
| `note` | Ephemeral scratchpad (demo) |
| `message_agent` | Ask another runtime agent (multi-agent) |

Enable tools by name in YAML — the registry resolves them at composition time.

---

## Configuration

```yaml
model: openai/gpt-4o-mini
system_prompt: >
  You are a helpful assistant with tools. Prefer tools for facts and
  computation instead of guessing.
max_tool_rounds: 5
personality:
  tone: professional
  style: concise
greeting: "Hello! How can I help?"
workspace_root: "."
sqlite_path: ".ai_agent/state.db"
chroma_path: ".ai_agent/chroma"
tools:
  - calculator
  - web_search
  - http_get
  - workspace_search
  - memory
  - retrieve
```

Multi-agent personas live under [`config/agents/`](config/agents/).

---

## Add a custom tool

```python
from ai_agent import BaseTool, ToolParameter, ToolResult

class EchoTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="echo",
            description="Return text in UPPERCASE.",
            parameters=[
                ToolParameter(name="text", type="string", description="Text", required=True)
            ],
        )

    async def execute(self, arguments: dict[str, object]) -> ToolResult:
        text = str(arguments.get("text", ""))
        return ToolResult(tool_name=self.name, success=True, output=text.upper())
```

Register at the composition root (see [`examples/custom_tool.py`](examples/custom_tool.py)).

---

## Quality bar

```bash
uv run pytest
uv run pytest --cov=src/ai_agent
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
uv run mutmut run      # high-value pure modules
uv run mutmut browse   # triage survivors
```

| Check | Role |
|---|---|
| **pytest** | Behavior with a scripted fake LLM — no API key in CI |
| **mypy** | `disallow_untyped_defs` on `src/` |
| **ruff** | Lint + format |
| **mutmut** | Mutation tests on validation / sandbox / registry |

Survivors are expected on a first baseline (many are equivalent string/bound tweaks). Kill important ones with focused assertions; don’t gate CI on 100% without triage.

---

## Project status

| Area | Maturity |
|---|---|
| Single-agent ReAct harness | Production-shaped reference |
| Multi-agent coordinator / researcher | Demo-ready |
| RAG | Optional extra; local Chroma |
| Observability / HITL / heavy sandbox | Intentionally out of scope (for now) |

---

## License

[MIT](LICENSE) © Eduardo Chiarotti ([pythonbyte](https://github.com/pythonbyte))
