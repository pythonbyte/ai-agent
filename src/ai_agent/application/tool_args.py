"""Pure tool-argument validation against ToolParameter specs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_agent.domain.tool import ToolParameter

SUPPORTED_TYPES = frozenset({"string", "number", "integer", "boolean"})


@dataclass(frozen=True, slots=True)
class ArgValidationResult:
    """Outcome of validating LLM-supplied tool arguments."""

    ok: bool
    arguments: dict[str, object]
    error: str | None = None


def validate_tool_arguments(
    parameters: list[ToolParameter],
    arguments: dict[str, object],
) -> ArgValidationResult:
    """
    Validate and lightly coerce tool arguments.

    Rules:
    - Reject unknown keys
    - Require every parameter marked required
    - Type-check string / number / integer / boolean
    """
    known = {p.name: p for p in parameters}
    unknown = sorted(set(arguments) - set(known))
    if unknown:
        return ArgValidationResult(
            ok=False,
            arguments={},
            error=f"Unknown arguments: {', '.join(unknown)}",
        )

    cleaned: dict[str, object] = {}
    for param in parameters:
        if param.name not in arguments:
            if param.required:
                return ArgValidationResult(
                    ok=False,
                    arguments={},
                    error=f"Missing required argument: {param.name}",
                )
            continue

        value = arguments[param.name]
        coerced, type_error = _coerce_value(param, value)
        if type_error is not None:
            return ArgValidationResult(ok=False, arguments={}, error=type_error)
        cleaned[param.name] = coerced

    return ArgValidationResult(ok=True, arguments=cleaned)


def _coerce_value(
    param: ToolParameter,
    value: Any,
) -> tuple[object, str | None]:
    expected = param.type.lower()
    if expected not in SUPPORTED_TYPES:
        return value, f"Unsupported parameter type for {param.name}: {param.type}"

    if expected == "string":
        if not isinstance(value, str):
            return value, f"Argument {param.name} must be a string"
        return value, None

    if expected == "boolean":
        if not isinstance(value, bool):
            return value, f"Argument {param.name} must be a boolean"
        return value, None

    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return value, f"Argument {param.name} must be an integer"
        return value, None

    # number: int or float, but not bool
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value, f"Argument {param.name} must be a number"
    return float(value), None
