"""In-memory scratchpad note tool — proves multi-tool stateful use."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class NoteTool(BaseTool):
    """
    Simple session scratchpad shared across tool calls.

    Useful for demos: write a note, then read it back in a later turn.
    """

    def __init__(self) -> None:
        super().__init__(
            name="note",
            description=(
                "Store or retrieve a short note in an in-memory scratchpad. "
                "action=write requires text; action=read returns the stored note."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Either 'write' or 'read'",
                    required=True,
                ),
                ToolParameter(
                    name="text",
                    type="string",
                    description="Note content when action=write",
                    required=False,
                ),
            ],
        )
        self._note: str | None = None

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        action = arguments.get("action")
        if action not in {"write", "read"}:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="action must be 'write' or 'read'",
            )

        if action == "write":
            text = arguments.get("text")
            if not isinstance(text, str) or not text.strip():
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="",
                    error="text is required when action=write",
                )
            self._note = text.strip()
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Saved note ({len(self._note)} chars).",
            )

        if self._note is None:
            return ToolResult(
                tool_name=self.name,
                success=True,
                output="(empty)",
            )
        return ToolResult(tool_name=self.name, success=True, output=self._note)
