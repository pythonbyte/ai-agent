"""Workspace search/read tool — sandboxed filesystem access."""

from __future__ import annotations

import json
from typing import Any

from ai_agent.domain.ports import WorkspaceReader
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class WorkspaceSearchTool(BaseTool):
    """Search or read files under a configured workspace root."""

    def __init__(self, reader: WorkspaceReader) -> None:
        super().__init__(
            name="workspace_search",
            description=(
                "Search or read files under the agent workspace. "
                "action=search finds query matches; action=read returns a file's text."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Either 'search' or 'read'",
                    required=True,
                ),
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search string when action=search",
                    required=False,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Relative file path when action=read",
                    required=False,
                ),
                ToolParameter(
                    name="glob",
                    type="string",
                    description="Optional glob for search (default **/*)",
                    required=False,
                ),
                ToolParameter(
                    name="max_bytes",
                    type="integer",
                    description="Max bytes for action=read (default 12000, max 200000)",
                    required=False,
                ),
                ToolParameter(
                    name="start_line",
                    type="integer",
                    description="Optional 1-based start line for action=read",
                    required=False,
                ),
                ToolParameter(
                    name="end_line",
                    type="integer",
                    description="Optional 1-based end line for action=read",
                    required=False,
                ),
            ],
        )
        self._reader = reader

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        action = str(arguments["action"])
        if action == "search":
            return self._search(arguments)
        if action == "read":
            return self._read(arguments)
        return ToolResult(
            tool_name=self.name,
            success=False,
            output="",
            error="action must be 'search' or 'read'",
        )

    def _search(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="query is required when action=search",
            )
        glob_pattern = arguments.get("glob")
        pattern = glob_pattern if isinstance(glob_pattern, str) and glob_pattern else "**/*"
        try:
            hits = self._reader.search(query.strip(), glob_pattern=pattern, max_results=20)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        payload = [{"path": path, "snippet": snippet} for path, snippet in hits]
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=json.dumps(payload, indent=2),
        )

    def _read(self, arguments: dict[str, Any]) -> ToolResult:
        path = arguments.get("path")
        if not isinstance(path, str) or not path.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="path is required when action=read",
            )
        max_bytes_raw = arguments.get("max_bytes", 12_000)
        try:
            max_bytes = int(max_bytes_raw) if max_bytes_raw is not None else 12_000
        except (TypeError, ValueError):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="max_bytes must be an integer",
            )
        max_bytes = max(1, min(max_bytes, 200_000))
        try:
            text = self._reader.read_text(path.strip(), max_bytes=max_bytes)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        start_raw = arguments.get("start_line")
        end_raw = arguments.get("end_line")
        if start_raw is not None or end_raw is not None:
            try:
                start = int(start_raw) if start_raw is not None else 1
                end = int(end_raw) if end_raw is not None else 10**9
            except (TypeError, ValueError):
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="",
                    error="start_line/end_line must be integers",
                )
            lines = text.splitlines(keepends=True)
            start_i = max(0, start - 1)
            end_i = min(len(lines), max(start, end))
            sliced = lines[start_i:end_i]
            text = f"(lines {start_i + 1}-{start_i + len(sliced)})\n{''.join(sliced)}"
        return ToolResult(tool_name=self.name, success=True, output=text)
