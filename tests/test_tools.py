"""Tests for ToolRegistry and built-in tools."""

from __future__ import annotations

import pytest

from ai_agent.application.registry import ToolRegistry
from ai_agent.tools.calculator import CalculatorTool, safe_eval
from ai_agent.tools.datetime_tool import CurrentTimeTool
from ai_agent.tools.note import NoteTool


class TestCalculator:
    def test_safe_eval_basic(self) -> None:
        assert safe_eval("2 + 2") == 4.0
        assert safe_eval("(3 + 1) * 2") == 8.0

    def test_safe_eval_rejects_names(self) -> None:
        with pytest.raises(ValueError):
            safe_eval("__import__('os').system('echo hi')")

    @pytest.mark.asyncio
    async def test_calculator_tool(self) -> None:
        tool = CalculatorTool()
        result = await tool.execute({"expression": "10 / 2"})
        assert result.success is True
        assert result.output == "5.0"

    @pytest.mark.asyncio
    async def test_calculator_missing_expression(self) -> None:
        tool = CalculatorTool()
        result = await tool.execute({})
        assert result.success is False
        assert result.error is not None


class TestCurrentTime:
    @pytest.mark.asyncio
    async def test_utc_default(self) -> None:
        tool = CurrentTimeTool()
        result = await tool.execute({})
        assert result.success is True
        assert "T" in result.output

    @pytest.mark.asyncio
    async def test_invalid_timezone(self) -> None:
        tool = CurrentTimeTool()
        result = await tool.execute({"timezone": "Not/AZone"})
        assert result.success is False


class TestNoteTool:
    @pytest.mark.asyncio
    async def test_write_and_read(self) -> None:
        tool = NoteTool()
        written = await tool.execute({"action": "write", "text": "ship it"})
        assert written.success is True
        read = await tool.execute({"action": "read"})
        assert read.output == "ship it"

    @pytest.mark.asyncio
    async def test_read_empty(self) -> None:
        tool = NoteTool()
        result = await tool.execute({"action": "read"})
        assert result.success is True
        assert result.output == "(empty)"


class TestToolRegistry:
    def test_empty_after_init(self) -> None:
        """Kills mutmut survivor: self._tools = None instead of {}."""
        registry = ToolRegistry()
        assert registry.names() == []
        assert registry.has("missing") is False
        assert registry.get("missing") is None
        assert registry.specs() == []

    def test_register_and_select(self) -> None:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        registry.register(CurrentTimeTool())
        selected = registry.select(["calculator"])
        assert selected.names() == ["calculator"]

    def test_duplicate_register(self) -> None:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        with pytest.raises(ValueError, match="Tool already registered: calculator") as exc_info:
            registry.register(CalculatorTool())
        assert "calculator" in str(exc_info.value)

    def test_select_unknown(self) -> None:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        with pytest.raises(KeyError):
            registry.select(["nope"])

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self) -> None:
        registry = ToolRegistry()
        result = await registry.execute("missing", {})
        assert result.success is False
        assert "Unknown tool" in (result.error or "")
