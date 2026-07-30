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
