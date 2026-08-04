"""Tests for async tool fan-out."""

from __future__ import annotations

import asyncio

import pytest

from ai_agent.domain.tool import BaseTool, ToolResult
from ai_agent.harness.registry import ToolRegistry


class _SlowTool(BaseTool):
    def __init__(
        self,
        name: str,
        delay: float,
        output: str,
        *,
        parallel_safe: bool = True,
    ) -> None:
        super().__init__(
            name=name,
            description="slow",
            parameters=[],
            parallel_safe=parallel_safe,
        )
        self._delay = delay
        self._output = output
        self.started_at: float | None = None

    async def execute(self, arguments: dict[str, object]) -> ToolResult:
        self.started_at = asyncio.get_event_loop().time()
        await asyncio.sleep(self._delay)
        return ToolResult(tool_name=self.name, success=True, output=self._output)


@pytest.mark.asyncio
async def test_execute_many_parallel() -> None:
    registry = ToolRegistry()
    registry.register(_SlowTool("a", 0.05, "A"))
    registry.register(_SlowTool("b", 0.05, "B"))
    started = asyncio.get_event_loop().time()
    results = await registry.execute_many(
        [
            ("a", {}),
            ("b", {}),
        ]
    )
    elapsed = asyncio.get_event_loop().time() - started
    assert [r.output for r in results] == ["A", "B"]
    assert elapsed < 0.09


@pytest.mark.asyncio
async def test_execute_many_serial_when_not_parallel_safe() -> None:
    registry = ToolRegistry()
    a = _SlowTool("a", 0.04, "A", parallel_safe=False)
    b = _SlowTool("b", 0.04, "B", parallel_safe=False)
    registry.register(a)
    registry.register(b)
    started = asyncio.get_event_loop().time()
    results = await registry.execute_many([("a", {}), ("b", {})])
    elapsed = asyncio.get_event_loop().time() - started
    assert [r.output for r in results] == ["A", "B"]
    assert elapsed >= 0.07
    assert a.started_at is not None and b.started_at is not None
    assert b.started_at >= a.started_at + 0.03
