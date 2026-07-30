"""Tests for conversation state."""

from __future__ import annotations

from ai_agent.domain.state import ConversationState
from ai_agent.domain.tool import ToolResult


class TestConversationState:
    def test_defaults(self) -> None:
        state = ConversationState()
        assert state.messages == []
        assert state.done is False
        assert state.greeting_sent is False

    def test_add_message(self) -> None:
        state = ConversationState()
        state.add_message("user", "hi")
        state.add_message("assistant", "hello")
        assert len(state.messages) == 2
        assert state.as_chat_dicts()[0] == {"role": "user", "content": "hi"}

    def test_mark_done(self) -> None:
        state = ConversationState()
        state.mark_done()
        assert state.done is True

    def test_tool_traces(self) -> None:
        state = ConversationState()
        state.tool_traces.append(ToolResult(tool_name="calculator", success=True, output="4"))
        assert state.tool_traces[0].output == "4"

    def test_as_chat_dicts_maps_tool_role_to_user(self) -> None:
        """OpenRouter rejects role=tool without tool_call_id / native tool_calls."""
        state = ConversationState()
        state.add_message("assistant", '{"kind":"call_tools"}')
        state.add_message(
            "tool",
            '{"tool":"calculator","success":true,"output":"4"}',
            tool_name="calculator",
        )
        wire = state.as_chat_dicts()
        assert wire[1]["role"] == "user"
        assert wire[1]["content"].startswith("[Observation from calculator]")
        assert "calculator" in wire[1]["content"]
