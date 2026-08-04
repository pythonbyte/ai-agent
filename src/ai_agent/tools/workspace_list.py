"""workspace_list — list files under the workspace."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import WorkspaceWriter
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class WorkspaceListTool(BaseTool):
    def __init__(self, writer: WorkspaceWriter) -> None:
        super().__init__(
            name="workspace_list",
            description="List relative file paths under the workspace (glob optional).",
            parameters=[
                ToolParameter(
                    name="glob_pattern",
                    type="string",
                    description="Glob under workspace root (default **/*)",
                    required=False,
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Max paths to return (default 200)",
                    required=False,
                ),
            ],
        )
        self._writer = writer

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        glob_pattern = str(arguments.get("glob_pattern") or "**/*")
        max_results_raw = arguments.get("max_results", 200)
        try:
            max_results = int(max_results_raw) if max_results_raw is not None else 200
        except (TypeError, ValueError):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="max_results must be an integer",
            )
        paths = self._writer.list_paths(glob_pattern=glob_pattern, max_results=max_results)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output="\n".join(paths) if paths else "(no files)",
        )
