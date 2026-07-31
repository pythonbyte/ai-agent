# Architecture overview

This kit is a **tool-using conversational agent** with Clean Architecture layers:

- Domain models and ports (no I/O)
- Application ReAct loop + ToolRegistry
- Infrastructure adapters (OpenRouter, SQLite, Chroma, WebSocket)
- Orchestration runtime for multi-agent sessions

## Tools

Built-in tools include calculator, current_time, http_get, workspace_search,
memory, and retrieve. Tools are selected by name in YAML config.

## Running

```bash
uv sync --all-extras
uv run ai-agent -c config/agent_config.yaml
```

Ingest docs for RAG:

```bash
uv run ai-agent ingest --docs docs/
```
