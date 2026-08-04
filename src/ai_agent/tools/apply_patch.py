"""apply_patch — apply a unified diff under PathPolicy."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import WorkspaceWriter
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class ApplyPatchTool(BaseTool):
    def __init__(self, writer: WorkspaceWriter) -> None:
        super().__init__(
            name="apply_patch",
            description=(
                "Apply a unified git-style diff to allowlisted paths. "
                "Prefer this over free-form writes."
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
        return ToolResult(
            tool_name=self.name,
            success=True,
            output="touched:\n" + "\n".join(touched),
        )
