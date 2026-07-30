"""Built-in tools and a factory for the default registry."""

from __future__ import annotations

from ai_agent.application.registry import ToolRegistry
from ai_agent.tools.calculator import CalculatorTool
from ai_agent.tools.datetime_tool import CurrentTimeTool
from ai_agent.tools.note import NoteTool

__all__ = [
    "CalculatorTool",
    "CurrentTimeTool",
    "NoteTool",
    "build_default_registry",
]


def build_default_registry() -> ToolRegistry:
    """Register all built-in tools into a fresh registry."""
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    registry.register(NoteTool())
    return registry
