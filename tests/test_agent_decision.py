"""Tests for AgentDecision coercion when models misuse kind."""

from __future__ import annotations

from ai_agent.domain.models import AgentDecision


def test_valid_call_tools_unchanged() -> None:
    decision = AgentDecision.model_validate(
        {
            "kind": "call_tools",
            "tool_calls": [
                {"name": "message_agent", "arguments": {"agent_id": "researcher", "message": "hi"}}
            ],
        }
    )
    assert decision.kind == "call_tools"
    assert decision.tool_calls[0].name == "message_agent"


def test_tool_name_as_kind_is_coerced() -> None:
    """Regression: models often set kind=message_agent instead of call_tools."""
    decision = AgentDecision.model_validate(
        {
            "kind": "message_agent",
            "agent_id": "researcher",
            "message": "Summarize https://example.com",
        }
    )
    assert decision.kind == "call_tools"
    assert len(decision.tool_calls) == 1
    assert decision.tool_calls[0].name == "message_agent"
    assert decision.tool_calls[0].arguments["agent_id"] == "researcher"
    assert "Summarize" in str(decision.tool_calls[0].arguments["message"])


def test_tool_name_kind_with_existing_tool_calls() -> None:
    decision = AgentDecision.model_validate(
        {
            "kind": "http_get",
            "tool_calls": [{"name": "http_get", "arguments": {"url": "https://x.com"}}],
        }
    )
    assert decision.kind == "call_tools"
    assert decision.tool_calls[0].name == "http_get"
