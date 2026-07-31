"""Built-in calculator tool."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Any

from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        bin_fn = _BIN_OPS.get(type(node.op))
        if bin_fn is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return float(bin_fn(_eval_node(node.left), _eval_node(node.right)))
    if isinstance(node, ast.UnaryOp):
        unary_fn = _UNARY_OPS.get(type(node.op))
        if unary_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return float(unary_fn(_eval_node(node.operand)))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval(expression: str) -> float:
    """Evaluate a basic arithmetic expression without exec/eval of arbitrary code."""
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree)


class CalculatorTool(BaseTool):
    """Evaluate arithmetic expressions (+ - * / ** %)."""

    def __init__(self) -> None:
        super().__init__(
            name="calculator",
            description="Evaluate a basic arithmetic expression and return the numeric result.",
            parameters=[
                ToolParameter(
                    name="expression",
                    type="string",
                    description="Arithmetic expression, e.g. '(12 + 3) * 2'",
                    required=True,
                )
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        expression = arguments.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="Missing required string argument: expression",
            )
        try:
            result = safe_eval(expression.strip())
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=str(result),
            )
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
