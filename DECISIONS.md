# Decisions

## The core idea

An agent is a loop: observe input, decide what to do, act (often via tools), remember, repeat.

This project implements that loop as a **generic tool-using agent**, not a specialized field-collection bot. Domain-specific behavior belongs in tools and prompts — not hard-coded into the core.

---

## Architecture

### Clean layers

| Layer | Responsibility |
|---|---|
| **Domain** | Models, `ConversationState`, `Tool` protocol, ports — no I/O |
| **Harness** | `Agent`, ReAct loop, `ToolRegistry`, arg / URL / Python guards |
| **Features** | Product use-cases (`brief`, `self_harness`) on top of the harness |
| **Adapters** | OpenRouter HTTP, SQLite, Chroma, workspace FS, WebSocket |
| **Orchestration** | Multi-agent runtime with inbox/outbox + synchronous `ask` |
| **Tools** | Thin adapters over ports, registered at the composition root |
| **Entrypoints** | CLI composition root |

Dependency direction always points inward. The agent loop depends on an `LLMPort` protocol, not on OpenRouter directly — so tests inject a fake LLM.

### Why a structured decision JSON?

Native provider tool-calling APIs differ. A single `AgentDecision` schema (`respond` | `call_tools` | `done`) keeps the loop provider-agnostic and easy to mock. Trade-off: one extra JSON-discipline prompt instead of first-class tool_calls fields from a specific SDK.

### Bounded tool rounds

`max_tool_rounds` prevents runaway loops when the model keeps calling tools. When the budget is exhausted, the agent returns a fallback summary instead of hanging.

### Context compaction (not truncation)

**Chose summarize-over-drop.** `ConversationState` keeps the full transcript (and SQLite can persist it). `SummarizingCompactor` builds a smaller *wire* view when `compaction.max_context_chars` is exceeded: keep system + recent messages, replace the middle with a summary. That mirrors the ARC-AGI harness lesson: rolling truncation deletes evidence; compaction preserves it in compressed form. Provider “retained reasoning” is separate and requires Responses-API-style features.

### Async-first runtime

Each agent runs in its own coroutine with dedicated queues. The WebSocket adapter and console CLI are interchangeable I/O surfaces over the same `Agent.step()`.

### Argument validation in the registry

Tool argument checks live in pure `validate_tool_arguments` and run inside `ToolRegistry.execute` before any tool I/O. Keeps tools dumb and mutation-tests focused on one module.

### RAG is a tool

Retrieval is `retrieve` over a `Retriever` port (Chroma or in-memory). No separate RAG loop — decide → retrieve → observe → respond.

### Multi-agent handoff

`AgentRuntime.ask` implements `AgentMessenger`: put on the specialist inbox, await the next `StepResult`. Only agents that receive `message_agent` in their registry can hand off (typically the coordinator).

---

## Trade-offs

### HTTP client vs OpenRouter SDK

**Chose `httpx`.** Full control over retries, timeouts, and response parsing. Avoids SDK churn for a thin Chat Completions call.

### SQLite for session + memory

**Chose stdlib `sqlite3`.** Durable sessions and key/value memory without an extra DB dependency. Temp JSON session reports remain as debug exports.

### Chroma as optional RAG extra

**Chose local Chroma** behind an optional `[rag]` extra so the core kit stays light. Tests use `InMemoryRetriever` + a fake embedder.

### In-memory note tool

**Kept for demos.** Prefer `memory` (SQLite) for durable facts. `note` remains as an ephemeral scratchpad.

### Greeting is deterministic

The first message is config-driven, not LLM-generated. Reliability beats variety for the opening turn.

### Mutation testing

**Chose `mutmut`** on high-value pure modules (`tool_args`, `url_safety`, workspace path checks, registry validation).

Survivors are expected on the first baseline — many are equivalent mutations (error-string wording, boundary tweaks). Workflow: `uv run mutmut run` → `uv run mutmut browse` → add focused tests for important survivors. Noise is reduced via `do_not_mutate_patterns`. Do not gate CI on 100% killed without triage.

---

## Personal Operator first

**Chose Research Desk before shopping/trading.** Same harness DNA (tools, memory, citations, light HITL) with a vertical that needs no Gmail/Calendar/checkout. Product surface: `operator.yaml` + `ai-agent brief`. Irreversible actions go through `request_approval` rather than a new `AgentDecision.kind`, keeping the decision schema stable.

## Self-Harness moonshot (experimental)

**Chose a guarded scaffold, not unsupervised self-modification.** Failures are mined into `HarnessPatch` surfaces limited to YAML (`system_prompt` append, `max_tool_rounds`). Accept runs pytest and requires a human CLI step. Arbitrary Python edits and auto-merge are out of v0 — matches “study while touching code” without claiming AGI. Framing and reading list live in the README moonshot section.

### Subprocess Python, not Docker

**Chose a deny-listed subprocess for `run_python`.** Enough for local agent computation (math, transforms) with timeout and output caps. Not a multi-tenant sandbox — escalate to containers when running untrusted code at scale.

## Self-Evolving Engineer + HarnessBank

**Thesis:** \(A_H = M \circ H\) with **M frozen**; only **H** evolves under verification ([HarnessBank](https://arxiv.org/abs/2607.13683)).

**Chose auto-publish PR for evolve (HITL optional).** `ai-agent evolve` runs the engineer persona: survey → plan → edit → `run_checks` → scoped commit → push → PR. Default uses `AutoApprovalGate`; pass `--approve` for console Y/n. Humans still merge on GitHub. PathPolicy jail blocks `.env`, `.git/`, and kernel modules (`path_policy`, platform merge surfaces). Commit scopes to TouchTracker paths only.

**Chose separate evolver ≠ task agent.** Gene Bank cells live under `.ai_agent/gene_bank/(where)__(why)/` with gated screening (validity → activation → significance → gain). Kernel \(K\) (policies, STOP, screening) is immutable to the evolver; surface \(X\) (prompts, YAML budgets) is mutable.

**Phase 2 organism:** `evolve-worker` + `FileScheduler` + `MergePolicy.may_merge` + CI wait via `gh`. STOP file under `.ai_agent/evolve/STOP` is the kill switch. Auto-merge never ships without policy.

**Ops:** structured `OpsEvent` JSONL + `ops events` / `ops replay` for cost/latency/success attribution at log level.

## What this is not

- Not an observability platform
- Not tied to a single framework beyond OpenAI-compatible HTTP
- Not a customer-support field collector (that can be a *tool* or a separate config, not the core)
- Not CrewAI/LangGraph glue — we compete on typed harness quality, not DX sugar
- Not unsupervised “no brakes” self-modification (evolver cannot mute \(K\))

---

## How AI coding tools were used

Pair-programmed with Cursor. Architecture and trade-offs were human decisions; boilerplate, tests, and refactors were collaborative. Every public API was reviewed for typing and testability.
