# AGENTS.md — conventions for humans and coding agents working in this repo

## Mission

This repository is a **typed agent harness** (`Agent = Model + Harness`), not a chatbot wrapper.
Prefer clear architecture, strict typing, and tests over framework magic.

## Architecture (dependency direction: inward only)

```text
entrypoints/  →  features/ + orchestration/ + tools/
                      ↓
                   harness/     (loop, registry, compaction, guards)
                      ↓
                   domain/      (models, ports, state — no I/O)
                      ↑
                   adapters/    (LLM, SQLite, FS, HTTP, WS — implement ports)
```

| Package | Own |
|---|---|
| `domain/` | Pure types, ports, `ConversationState` |
| `harness/` | ReAct loop, `ToolRegistry`, compaction, validation |
| `features/` | Product use-cases (`brief`, `self_harness`, `evolve`, `harness_bank`) |
| `adapters/` | External systems |
| `orchestration/` | Multi-agent runtime |
| `tools/` | Agent-facing tools over ports |
| `support/` | Shared helpers (console I/O) |
| `entrypoints/` | CLI composition root |

**Do not** import `adapters` or `entrypoints` from `domain`.
**Do not** put I/O in `domain` or business policy in `adapters`.

## Coding standards

- Python **3.12+**, `mypy` with `disallow_untyped_defs` on `src/`
- Prefer explicit types on public functions; use `Protocol` ports for DI
- Keep functions small; avoid deep nesting
- Failures of external deps are expected — log and return structured errors
- Never invent tool results in prompts; the harness observes tools

## Agent / harness behavior rules

1. **Model proposes, harness executes** — tools run only via `ToolRegistry.execute`
2. **Validate args** before tool I/O (`validate_tool_arguments`)
3. **Bound loops** with `max_tool_rounds`
4. **Context packing** — full history stays in `ConversationState`; wire view may be compacted (`SummarizingCompactor`). Prefer summarize over drop.
5. **SQLite** = durable session/memory retention across process restarts (not the same as provider “retained reasoning”)
6. **Self-Harness / HarnessBank** patches are gated; evolver must not edit kernel \(K\) (`PathPolicy`, `MergePolicy`, STOP, screening)
7. **`run_python`** is deny-listed subprocess — not a multi-tenant sandbox
8. **Evolve** publishes via PR + HITL; Phase 2 auto-merge only under `MergePolicy` + CI + no STOP file

## Kernel \(K\) vs surface \(X\)

| Immutable kernel \(K\) | Mutable surface \(X\) |
|---|---|
| PathPolicy / MergePolicy / STOP | System prompts, tool descriptions |
| Eval / screening / Gene Bank bookkeeping | YAML configs, `max_tool_rounds` |
| Approval / CI merge rules | Recovery snippets, knowledge injects |

## Tests

Mirror source layout under `tests/`:

```text
tests/domain/  tests/harness/  tests/features/  tests/adapters/
tests/orchestration/  tests/tools/  tests/support/
```

- No live network in CI — use `ScriptedLLM` and fakes
- Mutation testing (`mutmut`) targets pure high-value modules (`tool_args`, `url_safety`, `compaction`, `diff_apply`, `path_policy`, `merge_policy`, registry validation, workspace jail)

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
uv run mutmut run
```

## Config & secrets

- Agent behavior lives in `config/**/*.yaml`
- Secrets only in `.env` (`OPENROUTER_API_KEY`) — never commit
- Optional compaction:

```yaml
compaction:
  enabled: true
  max_context_chars: 48000
  keep_recent_messages: 12
  max_summary_chars: 4000
```

## PR / change expectations

- Match existing style; no drive-by refactors
- Add/adjust tests with behavior changes
- Update `README.md` / `DECISIONS.md` when architecture trade-offs change
- Keep CLI thin; put logic in harness/features

## Local run (quick)

```bash
uv sync --all-extras
uv run ai-agent -c config/agent_config.yaml
uv run ai-agent brief "topic"
uv run ai-agent evolve "add typed logging helpers" --approve
uv run ai-agent harness-bank list
uv run ai-agent --server --host 0.0.0.0
docker compose up --build   # WebSocket on :8765
```
