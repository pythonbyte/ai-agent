"""replace_in_file — unique string replace under PathPolicy (best for README bullets)."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import WorkspaceWriter
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult
from ai_agent.harness.touch_tracker import TouchTracker


class ReplaceInFileTool(BaseTool):
    def __init__(
        self,
        writer: WorkspaceWriter,
        tracker: TouchTracker | None = None,
    ) -> None:
        super().__init__(
            name="replace_in_file",
            description=(
                "Replace exactly one unique old_string with new_string in an "
                "allowlisted file. Best for adding a README bullet: include a "
                "nearby unique anchor in old_string and the same text plus the "
                "new line in new_string. Prefer this over apply_patch/write_file "
                "for small doc edits."
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Relative path (e.g. README.md)",
                    required=True,
                ),
                ToolParameter(
                    name="old_string",
                    type="string",
                    description="Exact unique text to find",
                    required=True,
                ),
                ToolParameter(
                    name="new_string",
                    type="string",
                    description="Replacement text (usually old_string + addition)",
                    required=True,
                ),
            ],
        )
        self._writer = writer
        self._tracker = tracker

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = str(arguments.get("path") or "").strip()
        old = arguments.get("old_string")
        new = arguments.get("new_string")
        if not path:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="path is required",
            )
        if not isinstance(old, str) or not old:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="old_string is required",
            )
        if not isinstance(new, str):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="new_string must be a string",
            )
        try:
            written = self._writer.replace_in_file(path, old, new)
        except (ValueError, PermissionError, OSError, FileNotFoundError) as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        if self._tracker is not None:
            self._tracker.record(written)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=f"updated {written}",
        )
