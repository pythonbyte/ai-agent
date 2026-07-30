"""Example: wire a custom tool into the agent."""

from __future__ import annotations

import asyncio

from ai_agent import (
    Agent,
    AgentConfig,
    BaseTool,
    OpenRouterLLM,
    Personality,
    ToolParameter,
    ToolResult,
    build_default_registry,
)


class EchoTool(BaseTool):
    """Trivial custom tool — uppercases input text."""

    def __init__(self) -> None:
        super().__init__(
            name="echo",
            description="Return the given text in UPPERCASE.",
            parameters=[
                ToolParameter(
                    name="text",
                    type="string",
                    description="Text to echo",
                    required=True,
                )
            ],
        )

    async def execute(self, arguments: dict[str, object]) -> ToolResult:
        text = arguments.get("text")
        if not isinstance(text, str):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="text must be a string",
            )
        return ToolResult(tool_name=self.name, success=True, output=text.upper())


async def main() -> None:
    config = AgentConfig(
        model="openai/gpt-4o-mini",
        system_prompt="You are a demo agent. Use tools when helpful.",
        tools=["calculator", "echo"],
        personality=Personality(tone="friendly", style="concise"),
        greeting="Hi! I can calculate or echo text.",
    )
    registry = build_default_registry()
    registry.register(EchoTool())
    selected = registry.select(config.tools)

    agent = Agent(
        config=config,
        llm=OpenRouterLLM(model=config.model),
        registry=selected,
    )
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
