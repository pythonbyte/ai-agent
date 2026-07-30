# ai-agent

A typed, clean-architecture **tool-using conversational agent** kit.

Not a form-filling bot. The core loop is generic: observe → decide → act (tools) → respond, with YAML config, pluggable tools, and a multi-agent async runtime.

## Why this exists

A reusable reference agent for real projects and hiring conversations:

- Clear **Domain / Application / Infrastructure** boundaries
- Strict typing (`mypy`), linting (`ruff`), and a solid pytest suite
- Custom tools in ~10 lines via `BaseTool`
- Reproducible runs: config + model + tool list are explicit

## Architecture

```text
src/ai_agent/
├── domain/           # pure models + Tool protocol (no I/O)
├── application/      # Agent + ReAct tool loop + ToolRegistry
├── infrastructure/   # OpenRouter LLM, YAML loader, WebSocket
├── orchestration/    # multi-agent runtime (inbox/outbox)
├── tools/            # built-ins: calculator, current_time, note
└── cli.py
```

```text
User / WebSocket → CLI or Server → AgentRuntime → Agent loop
                                              ├─ LLMPort (OpenRouter)
                                              └─ ToolRegistry → tools
```

## Quick start

```bash
git clone https://github.com/pythonbyte/ai-agent.git
cd ai-agent

# with uv (recommended)
uv sync --all-extras
cp .env.example .env   # set OPENROUTER_API_KEY

uv run ai-agent -c config/agent_config.yaml
```

Or with pip:

```bash
pip install -e ".[dev]"
ai-agent -c config/agent_config.yaml
```

### WebSocket mode

```bash
uv run ai-agent --server -v
# another terminal:
websocat ws://localhost:8765
```

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
tools:
  - calculator
  - current_time
  - note
```

## Adding a custom tool

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

# registry.register(EchoTool())
```

See [`examples/custom_tool.py`](examples/custom_tool.py).

## Testing & quality

```bash
uv run pytest
uv run pytest --cov=src/ai_agent
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

Unit tests mock the LLM — no API key required for CI.

## Design notes

See [DECISIONS.md](DECISIONS.md) for architecture trade-offs (tool loop vs specialty bots, HTTP LLM adapter, bounded tool rounds).

## License

MIT
