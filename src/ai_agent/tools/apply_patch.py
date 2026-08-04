"""apply_patch — apply a unified diff under PathPolicy."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import WorkspaceWriter
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult
from ai_agent.harness.touch_tracker import TouchTracker


class ApplyPatchTool(BaseTool):
    def __init__(
        self,
        writer: WorkspaceWriter,
        tracker: TouchTracker | None = None,
    ) -> None:
        super().__init__(
            name="apply_patch",
            description=(
                "Apply a unified git-style diff to allowlisted paths. "
                "Context lines must match the file EXACTLY. "
                "If this fails twice, use write_file instead."
            ),
            parameters=[
                ToolParameter(
                    name="patch",
                    type="string",
                    description="Unified diff text (diff --git ...)",
                    required=True,
                ),
            ],
        )
        self._writer = writer
        self._tracker = tracker

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        patch = str(arguments.get("patch") or "")
        if not patch.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="patch is required",
            )
        try:
            touched = self._writer.apply_unified_diff(patch)
        except (ValueError, PermissionError, OSError) as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        if self._tracker is not None:
            self._tracker.record_many(touched)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output="touched:\n" + "\n".join(touched),
        )
