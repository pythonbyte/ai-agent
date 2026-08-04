"""write_file — policy-jailed full-file write (simpler than unified diffs)."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import WorkspaceWriter
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult
from ai_agent.harness.touch_tracker import TouchTracker


class WriteFileTool(BaseTool):
    def __init__(
        self,
        writer: WorkspaceWriter,
        tracker: TouchTracker | None = None,
    ) -> None:
        super().__init__(
            name="write_file",
            description=(
                "Write full file contents under PathPolicy allowlist. "
                "Prefer this for small README/docs edits when apply_patch keeps "
                "failing context mismatches. Pass the COMPLETE new file text."
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Relative path (e.g. README.md)",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Full new file contents",
                    required=True,
                ),
            ],
        )
        self._writer = writer
        self._tracker = tracker

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = str(arguments.get("path") or "").strip()
        content = arguments.get("content")
        if not path:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="path is required",
            )
        if not isinstance(content, str):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="content must be a string",
            )
        try:
            written = self._writer.write_text(path, content)
        except (ValueError, PermissionError, OSError) as exc:
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
            output=f"wrote {written} ({len(content.encode('utf-8'))} bytes)",
        )
