"""Tests for pure tool argument validation."""

from __future__ import annotations

from ai_agent.application.tool_args import validate_tool_arguments
from ai_agent.domain.tool import ToolParameter


def _params(*items: ToolParameter) -> list[ToolParameter]:
    return list(items)


class TestValidateToolArguments:
    def test_ok_string(self) -> None:
        params = _params(ToolParameter(name="text", type="string", description="t", required=True))
        result = validate_tool_arguments(params, {"text": "hi"})
        assert result.ok is True
        assert result.arguments == {"text": "hi"}

    def test_missing_required(self) -> None:
        params = _params(ToolParameter(name="text", type="string", description="t", required=True))
        result = validate_tool_arguments(params, {})
        assert result.ok is False
        assert "Missing required" in (result.error or "")

    def test_optional_omitted(self) -> None:
        params = _params(
            ToolParameter(name="timezone", type="string", description="tz", required=False)
        )
        result = validate_tool_arguments(params, {})
        assert result.ok is True
        assert result.arguments == {}

    def test_unknown_key(self) -> None:
        params = _params(ToolParameter(name="text", type="string", description="t", required=True))
        result = validate_tool_arguments(params, {"text": "hi", "extra": 1})
        assert result.ok is False
        assert "Unknown arguments" in (result.error or "")

    def test_wrong_string_type(self) -> None:
        params = _params(ToolParameter(name="text", type="string", description="t", required=True))
        result = validate_tool_arguments(params, {"text": 1})
        assert result.ok is False
        assert "must be a string" in (result.error or "")

    def test_integer_rejects_bool(self) -> None:
        params = _params(ToolParameter(name="n", type="integer", description="n", required=True))
        result = validate_tool_arguments(params, {"n": True})
        assert result.ok is False

    def test_integer_ok(self) -> None:
        params = _params(ToolParameter(name="n", type="integer", description="n", required=True))
        result = validate_tool_arguments(params, {"n": 3})
        assert result.ok is True
        assert result.arguments["n"] == 3

    def test_number_coerces_int(self) -> None:
        params = _params(ToolParameter(name="x", type="number", description="x", required=True))
        result = validate_tool_arguments(params, {"x": 2})
        assert result.ok is True
        assert result.arguments["x"] == 2.0

    def test_boolean_ok(self) -> None:
        params = _params(ToolParameter(name="flag", type="boolean", description="f", required=True))
        result = validate_tool_arguments(params, {"flag": False})
        assert result.ok is True
        assert result.arguments["flag"] is False

    def test_boolean_rejects_string(self) -> None:
        params = _params(ToolParameter(name="flag", type="boolean", description="f", required=True))
        result = validate_tool_arguments(params, {"flag": "yes"})
        assert result.ok is False

    def test_number_rejects_bool(self) -> None:
        params = _params(ToolParameter(name="x", type="number", description="x", required=True))
        result = validate_tool_arguments(params, {"x": True})
        assert result.ok is False
        assert "must be a number" in (result.error or "")

    def test_number_rejects_string(self) -> None:
        params = _params(ToolParameter(name="x", type="number", description="x", required=True))
        result = validate_tool_arguments(params, {"x": "1.5"})
        assert result.ok is False

    def test_number_accepts_float(self) -> None:
        params = _params(ToolParameter(name="x", type="number", description="x", required=True))
        result = validate_tool_arguments(params, {"x": 1.5})
        assert result.ok is True
        assert result.arguments["x"] == 1.5

    def test_unsupported_type(self) -> None:
        params = _params(ToolParameter(name="x", type="array", description="x", required=True))
        result = validate_tool_arguments(params, {"x": []})
        assert result.ok is False
        assert "Unsupported" in (result.error or "")

    def test_integer_rejects_float(self) -> None:
        params = _params(ToolParameter(name="n", type="integer", description="n", required=True))
        result = validate_tool_arguments(params, {"n": 1.2})
        assert result.ok is False
