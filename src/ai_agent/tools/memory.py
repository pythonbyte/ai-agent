"""Durable key/value memory tool backed by a MemoryStore port."""

from __future__ import annotations

import json
from typing import Any

from ai_agent.domain.ports import MemoryStore
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class MemoryTool(BaseTool):
    """Persist facts across turns and sessions via MemoryStore."""

    def __init__(self, store: MemoryStore) -> None:
        super().__init__(
            name="memory",
            description=(
                "Durable key/value memory. "
                "action=write stores value; action=read fetches; action=list lists keys."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="One of write, read, list",
                    required=True,
                ),
                ToolParameter(
                    name="key",
                    type="string",
                    description="Memory key for write/read; prefix for list",
                    required=False,
                ),
                ToolParameter(
                    name="value",
                    type="string",
                    description="Value when action=write",
                    required=False,
                ),
            ],
        )
        self._store = store

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        action = str(arguments["action"])
        if action == "write":
            return self._write(arguments)
        if action == "read":
            return self._read(arguments)
        if action == "list":
            return self._list(arguments)
        return ToolResult(
            tool_name=self.name,
            success=False,
            output="",
            error="action must be write, read, or list",
        )

    def _write(self, arguments: dict[str, Any]) -> ToolResult:
        key = arguments.get("key")
        value = arguments.get("value")
        if not isinstance(key, str) or not key.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="key is required when action=write",
            )
        if not isinstance(value, str):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="value is required when action=write",
            )
        self._store.put(key.strip(), value)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=f"Stored memory key={key.strip()}",
        )

    def _read(self, arguments: dict[str, Any]) -> ToolResult:
        key = arguments.get("key")
        if not isinstance(key, str) or not key.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="key is required when action=read",
            )
        value = self._store.get(key.strip())
        if value is None:
            return ToolResult(
                tool_name=self.name,
                success=True,
                output="(missing)",
            )
        return ToolResult(tool_name=self.name, success=True, output=value)

    def _list(self, arguments: dict[str, Any]) -> ToolResult:
        prefix = arguments.get("key")
        prefix_str = prefix.strip() if isinstance(prefix, str) else ""
        keys = self._store.list_keys(prefix_str)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=json.dumps(keys),
        )
