"""Tool registry — resolve tools by name for the agent loop."""

from __future__ import annotations

import logging

from ai_agent.application.tool_args import validate_tool_arguments
from ai_agent.domain.tool import Tool, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Name → Tool map used by the agent loop.

    Registration happens at the composition root (CLI / examples), not inside
    the domain — so custom tools plug in without touching core logic.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    def select(self, names: list[str]) -> ToolRegistry:
        """Return a new registry containing only the named tools."""
        selected = ToolRegistry()
        missing: list[str] = []
        for name in names:
            tool = self._tools.get(name)
            if tool is None:
                missing.append(name)
                continue
            selected.register(tool)
        if missing:
            raise KeyError(f"Unknown tools in config: {', '.join(missing)}")
        return selected

    async def execute(self, name: str, arguments: dict[str, object]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("Unknown tool requested: %s", name)
            return ToolResult(
                tool_name=name,
                success=False,
                output="",
                error=f"Unknown tool: {name}",
            )

        validation = validate_tool_arguments(tool.parameters, arguments)
        if not validation.ok:
            logger.warning(
                "Tool argument validation failed name=%s error=%s",
                name,
                validation.error,
            )
            return ToolResult(
                tool_name=name,
                success=False,
                output="",
                error=validation.error or "Invalid arguments",
            )

        try:
            return await tool.execute(validation.arguments)
        except Exception as exc:  # noqa: BLE001 — surface tool failures to the LLM
            logger.exception("Tool %s failed", name)
            return ToolResult(
                tool_name=name,
                success=False,
                output="",
                error=str(exc),
            )
