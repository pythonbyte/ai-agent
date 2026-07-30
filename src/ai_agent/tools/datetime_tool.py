"""Built-in current-time tool."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class CurrentTimeTool(BaseTool):
    """Return the current date/time, optionally in a named IANA timezone."""

    def __init__(self) -> None:
        super().__init__(
            name="current_time",
            description=(
                "Get the current date and time. "
                "Optional timezone is an IANA name like 'America/Sao_Paulo'."
            ),
            parameters=[
                ToolParameter(
                    name="timezone",
                    type="string",
                    description="IANA timezone (default: UTC)",
                    required=False,
                )
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tz_name = arguments.get("timezone") or "UTC"
        if not isinstance(tz_name, str):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="timezone must be a string",
            )
        try:
            tz = ZoneInfo(tz_name) if tz_name != "UTC" else UTC
        except ZoneInfoNotFoundError:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=f"Unknown timezone: {tz_name}",
            )

        now = datetime.now(tz)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=now.isoformat(),
        )
