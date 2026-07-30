# Decisions

## The core idea

An agent is a loop: observe input, decide what to do, act (often via tools), remember, repeat.

This project implements that loop as a **generic tool-using agent**, not a specialized field-collection bot. Domain-specific behavior belongs in tools and prompts — not hard-coded into the core.

---

## Architecture

### Clean layers

| Layer | Responsibility |
|---|---|
| **Domain** | Models, `ConversationState`, `Tool` protocol — no I/O |
| **Application** | `Agent`, ReAct tool loop, `ToolRegistry` |
| **Infrastructure** | OpenRouter HTTP client, YAML config, WebSocket |
| **Orchestration** | Multi-agent runtime with isolated inbox/outbox queues |
| **Tools** | Built-in adapters registered at the composition root |

Dependency direction always points inward. The agent loop depends on an `LLMPort` protocol, not on OpenRouter directly — so tests inject a fake LLM.

### Why a structured decision JSON?

Native provider tool-calling APIs differ. A single `AgentDecision` schema (`respond` | `call_tools` | `done`) keeps the loop provider-agnostic and easy to mock. Trade-off: one extra JSON-discipline prompt instead of first-class tool_calls fields from a specific SDK.

### Bounded tool rounds

`max_tool_rounds` prevents runaway loops when the model keeps calling tools. When the budget is exhausted, the agent returns a fallback summary instead of hanging.

### Async-first runtime

Each agent runs in its own coroutine with dedicated queues. The WebSocket adapter and console CLI are interchangeable I/O surfaces over the same `Agent.step()`.

---

## Trade-offs

### HTTP client vs OpenRouter SDK

**Chose `httpx`.** Full control over retries, timeouts, and response parsing. Avoids SDK churn for a thin Chat Completions call.

### In-memory note tool

**Chose simplicity.** The `note` tool proves multi-tool stateful use without a database. Production apps would inject a real store behind the same `Tool` protocol.

### Greeting is deterministic

The first message is config-driven, not LLM-generated. Reliability beats variety for the opening turn.

---

## What this is not

- Not an observability platform
- Not tied to a single framework beyond OpenAI-compatible HTTP
- Not a customer-support field collector (that can be a *tool* or a separate config, not the core)

---

## How AI coding tools were used

Pair-programmed with Cursor. Architecture and trade-offs were human decisions; boilerplate, tests, and refactors were collaborative. Every public API was reviewed for typing and testability.
