# ai-agent

**A typed, self-evolving agent harness for tool-using LLMs.**

> **This is a self-evolving agent:** it can inspect the repository, make scoped improvements, run checks, and propose changes as pull requests.
>
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
| **Decide → act → observe loop** | Done | Bounded ReAct loop (`respond` / `call_tools` / `done`) with `max_tool_rounds` | [`harness/loop.py`](src/ai_agent/harness/loop.py) |
| **Structured decisions** | Done | Pydantic `AgentDecision`; coerces tool-name-as-kind mistakes from LLMs | [`domain/models.py`](src/ai_agent/domain/models.py) |
| **Tool registry & dispatch** | Done | Name → tool map, config `select()`, safe `execute()` | [`harness/registry.py`](src/ai_agent/harness/registry.py) |
| **Argument validation** | Done | Required / type / unknown-key checks before any tool I/O | [`harness/tool_args.py`](src/ai_agent/harness/tool_args.py) |
| **Web tools** | Done | `web_search` (DuckDuckGo) + `http_get` (http/https only, size limits) | [`tools/`](src/ai_agent/tools/) · [`adapters/`](src/ai_agent/adapters/) |
| **Workspace tools** | Done | Sandboxed `workspace_search` / read under `workspace_root` | [`adapters/workspace_fs.py`](src/ai_agent/adapters/workspace_fs.py) |
| **Session state** | Done | Per-conversation messages + tool traces; finished sessions restart cleanly | [`domain/state.py`](src/ai_agent/domain/state.py) · [`orchestration/runtime.py`](src/ai_agent/orchestration/runtime.py) |
| **Durable memory** | Done | SQLite KV `memory` tool + session persistence | [`adapters/sqlite_store.py`](src/ai_agent/adapters/sqlite_store.py) |
| **RAG as a tool** | Done | Local Chroma (+ in-memory tests); `ai-agent ingest --docs` | [`adapters/chroma_retriever.py`](src/ai_agent/adapters/chroma_retriever.py) |
| **Multi-agent handoff** | Done | Coordinator → `message_agent` → researcher (sync ask + timeout) | [`orchestration/runtime.py`](src/ai_agent/orchestration/runtime.py) · [`config/agents/`](config/agents/) |
| **Serving surfaces** | Done | Console CLI, WebSocket chat (`--server`), multi-agent demo | [`entrypoints/cli.py`](src/ai_agent/entrypoints/cli.py) · [`adapters/server.py`](src/ai_agent/adapters/server.py) |
| **Guardrails (light)** | Done | URL scheme allowlist, path jail, AST calculator, Python deny-list + subprocess timeout | `url_safety` · `workspace_fs` · `calculator` · `python_guard` |
| **Provider portability** | Done | `LLMPort` + httpx OpenRouter adapter (no SDK lock-in) | [`adapters/llm.py`](src/ai_agent/adapters/llm.py) |
| **Research Desk** | Done | Personal Operator persona + `brief` → cited markdown under `briefs/` | [`config/agents/operator.yaml`](config/agents/operator.yaml) · [`features/brief`](src/ai_agent/features/brief/service.py) |
| **HITL approvals** | Done | `request_approval` tool + optional `brief --approve` (console Y/n) | [`tools/request_approval.py`](src/ai_agent/tools/request_approval.py) · [`adapters/approval.py`](src/ai_agent/adapters/approval.py) |
| **Code execution** | Done | `run_python` — subprocess + AST deny-list (not full container sandbox) | [`tools/run_python.py`](src/ai_agent/tools/run_python.py) · [`harness/python_guard.py`](src/ai_agent/harness/python_guard.py) |
| **Self-Harness (experimental)** | Scaffold | Mine failures → propose YAML patches → human `accept` after pytest | [`features/self_harness`](src/ai_agent/features/self_harness/service.py) |
| **Context compaction** | Done | Summarize older turns under a char budget; keep full history in state | [`harness/compaction.py`](src/ai_agent/harness/compaction.py) |
| **Runtime graph** | Done | `AgentFactory`, `spawn_agent`, depth/child budgets, async `execute_many` | [`orchestration/`](src/ai_agent/orchestration/) · [`harness/registry.py`](src/ai_agent/harness/registry.py) |
| **Self-Evolving Engineer** | Done | `evolve` → plan/patch/checks → scoped commit → push → PR (optional `--approve` HITL) | [`features/evolve`](src/ai_agent/features/evolve/) · [`config/agents/engineer.yaml`](config/agents/engineer.yaml) |
- Evolve artifacts live under `.ai_agent/evolve/<run_id>/`.
| **HarnessBank Gene Bank** | Done (v1) | `(where)×(why)` cells + gated screening stubs; evolver ≠ task agent | [`features/harness_bank`](src/ai_agent/features/harness_bank/) |
| **Organism worker (Phase 2)** | Done | CI wait, `MergePolicy`, file scheduler, STOP kill switch | [`features/evolve/organism.py`](src/ai_agent/features/evolve/organism.py) |
| **Ops metrics** | Done (log) | JSONL `OpsEvent`, replay/compare hooks | [`harness/ops_metrics.py`](src/ai_agent/harness/ops_metrics.py) |
| **OS / container sandbox** | — | Scoped limits only (not Docker/Firecracker) | Roadmap |

**Model (not harness):** whatever you set in YAML (`openai/gpt-4o-mini`, etc.) via OpenRouter.

---

## Architecture

```text
src/ai_agent/
├── domain/           # models, ConversationState, Tool protocol, ports
├── harness/          # Agent, ReAct loop, ToolRegistry, guards
├── features/         # brief, self_harness, evolve, harness_bank
├── adapters/         # OpenRouter, SQLite, Chroma, DuckDuckGo, FS, git, gh, WebSocket
├── orchestration/    # multi-agent runtime + AgentFactory / spawn
├── tools/            # agent-facing tools over ports
├── support/          # shared helpers (console I/O)
└── entrypoints/      # CLI composition root
```

```text
                  ┌─────────────────────────────────────────┐
  User / WS  ───► │  AgentRuntime (orchestration)           │
                  │    inbox → Agent.step → outbox / spawn  │
                  └───────────────┬─────────────────────────┘
                                  │
                  ┌───────────────▼─────────────────────────┐
                  │  Harness loop (application)             │
                  │  decide → ToolRegistry (gather) → obs   │
                  └───────┬─────────────────────┬───────────┘
                          │                     │
                 LLMPort (model)         tools → ports → infra
                 OpenRouter              search / FS / git / PR / RAG
```

Dependency rule: **inward only**. The loop depends on protocols, never on httpx/Chroma/SQLite directly. See [DECISIONS.md](DECISIONS.md). Marketing line: **Agent = Model + Harness—and the harness can evolve under proof.**

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
| Research operator | `uv run ai-agent -c config/agents/operator.yaml` | Interactive Research Desk |
| One-shot brief | `uv run ai-agent brief "agent harness"` | Writes `briefs/YYYYMMDD_slug.md` |
| Brief + approve | `uv run ai-agent brief "topic" --approve` | Console Y/n before write |
| **Evolve (engineer)** | `uv run ai-agent evolve "…"` | Auto branch → commit → push → PR (`--approve` = HITL) |
| Evolve worker | `uv run ai-agent evolve-worker [--auto-merge]` | Phase 2 organism tick |
| HarnessBank | `uv run ai-agent harness-bank list\|screen\|compare` | Gene Bank + screening |
| Ops | `uv run ai-agent ops events` / `ops replay <path>` | Metrics + trace replay |
| WebSocket | `uv run ai-agent --server -v` then `websocat ws://localhost:8765` | Chat-style plain text replies |
| Docker WebSocket | `docker compose up --build` then `websocat ws://localhost:8765` | Agent runs in container; terminal client on host |
| Multi-agent | `uv run ai-agent --multi-agent -v` | Coordinator + researcher handoff |
| RAG ingest | `uv run ai-agent ingest --docs docs/` | Needs `[rag]` extra |
| Harness propose | `uv run ai-agent harness propose` | Mine `.ai_agent/failures` → `proposals/` |
| Harness accept | `uv run ai-agent harness accept <id>` | Pytest gate, then merge into YAML |

---

## Personal Operator / Research Desk

First product vertical on this harness: a **research operator** that turns a topic into a cited brief.

```bash
uv run ai-agent brief "agent harness"
# → briefs/20260731_agent-harness.md  (Summary / Key findings / Sources / Open questions)

uv run ai-agent -c config/agents/operator.yaml   # interactive
```

The operator prefers `web_search` → `http_get` → local `retrieve` / `workspace_search`, remembers prefs via `memory` (`pref.*` keys), and never invents sources. Optional `--approve` gates publication. Irreversible future actions use the `request_approval` tool.

---

## Moonshot: Self-Harness

Industry frontier (not “solved”): a fixed model improves the **software around itself** — prompts, tool descriptions, loop budgets — from execution evidence, without weight updates. Canonical loop: weakness mining → harness proposal → validation (held-in improves, held-out does not regress).

**Reading path**

| Resource | Why |
|---|---|
| [Self-Harness (arXiv)](https://arxiv.org/abs/2606.09498) | Core paradigm + results |
| [Lil’Log — Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness/) | Map of self-improvement vs weight updates |
| [LangChain — Anatomy of an Agent Harness](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness) | Agent = Model + Harness vocabulary |
| [Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Long-horizon reliability |

**Scaffold in this repo (human-gated):** failures auto-log on step exceptions; `harness propose` writes a JSON patch (prompt append / `max_tool_rounds` only); `harness accept` runs a pytest subset then merges into YAML. **No auto-merge. No arbitrary Python edits in v0.**

```bash
uv run ai-agent harness record-failure "Timed out waiting for researcher"
uv run ai-agent harness propose
uv run ai-agent harness accept patch_… -c config/agents/operator.yaml
```

Upgrade path: **HarnessBank** Gene Bank + gated screening (`harness-bank screen`) and the **Self-Evolving Engineer** (`evolve`) for code PRs under PathPolicy. See [HarnessBank (arXiv:2607.13683)](https://arxiv.org/abs/2607.13683).

---

## Self-Evolving Engineer

```bash
uv run ai-agent evolve "add PathPolicy unit tests"
# optional HITL: add --approve
# → .ai_agent/evolve/<run_id>/{run.json,plan.md,result.json}
# → branch + PR after local checks (human merges)

uv run ai-agent evolve-worker              # schedule next wake; respect STOP
uv run ai-agent evolve-worker --auto-merge # Phase 2: CI + MergePolicy only
```

Touch `.ai_agent/evolve/STOP` to halt forever-loops.

---

## Built-in tools

| Tool | Purpose |
|---|---|
| `web_search` | DuckDuckGo search (titles, URLs, snippets) |
| `http_get` | Fetch http(s) page text (timeout + size cap) |
| `workspace_search` | Search / read files under `workspace_root` |
| `workspace_list` | List paths (engineer) |
| `apply_patch` | Unified diff under PathPolicy |
| `run_checks` | pytest / ruff / mypy presets |
| `git_status` / `git_diff` / `git_commit` | Git survey + approved commit |
| `open_pull_request` | Push branch + `gh pr create` (approved) |
| `spawn_agent` | Dynamic role spawn with depth/child budgets |
| `retrieve` | Semantic search over ingested docs (Chroma) |
| `memory` | Durable key/value facts (SQLite) |
| `calculator` | Safe AST arithmetic |
| `run_python` | Run short Python snippets (subprocess + import/call deny-list) |
| `current_time` | Clock / timezone |
| `note` | Ephemeral scratchpad (demo) |
| `message_agent` | Ask another runtime agent (multi-agent) |
| `request_approval` | Pause for human Y/n before irreversible actions |

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
  - run_python
  - web_search
  - http_get
  - workspace_search
  - memory
  - retrieve
compaction:
  enabled: true
  max_context_chars: 48000
  keep_recent_messages: 12
  max_summary_chars: 4000
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

## Run in Docker (terminal ↔ container)

Architecture:

```text
Your terminal  --WebSocket-->  localhost:8765  -->  Docker (ai-agent --server)
```

The CLI console (`ai-agent` without `--server`) needs a TTY inside the container and is awkward for “type on host → reply from Docker.” Use the **WebSocket server** instead.

```bash
# 1) Ensure .env has OPENROUTER_API_KEY
cp -n .env.example .env

# 2) Start the agent server in Docker
docker compose up --build

# 3) From another terminal on the host, chat:
websocat ws://localhost:8765
# type a message, Enter → agent reply comes back as plain text
```

Without `websocat`:

```bash
# one-shot with Python
python - <<'PY'
import asyncio, websockets
async def main():
    async with websockets.connect("ws://localhost:8765") as ws:
        print(await ws.recv())          # greeting
        await ws.send("What is 2+2? Use tools if needed.")
        print(await ws.recv())
asyncio.run(main())
PY
```

Operator persona in Docker:

```bash
docker compose run --service-ports agent \
  ai-agent --server --host 0.0.0.0 --port 8765 -c config/agents/operator.yaml -v
```

**Requirement:** server must listen on `0.0.0.0` (compose already does). `localhost` inside the container would not accept host connections.

---

## Quality bar

Tests mirror source packages under `tests/` (`domain/`, `harness/`, `features/`, …). See [AGENTS.md](AGENTS.md).

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
| Research Desk / Personal Operator | Shipped (`brief` + operator YAML) |
| Multi-agent coordinator / researcher | Demo-ready |
| RAG | Optional extra; local Chroma |
| HITL approvals | Light scaffold (`request_approval` + brief `--approve`) |
| Self-Harness | Experimental propose/accept only — human gate required |
| Observability / heavy sandbox | Intentionally out of scope (for now) |

---

## License

[MIT](LICENSE) © Eduardo Chiarotti ([pythonbyte](https://github.com/pythonbyte))
