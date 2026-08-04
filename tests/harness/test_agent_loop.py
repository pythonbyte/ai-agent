"""Tests for the generic agent tool loop (mocked LLM)."""

from __future__ import annotations

import pytest

from ai_agent.domain.models import AgentConfig, AgentDecision
from ai_agent.domain.state import ConversationState
from tests.conftest import ScriptedLLM, decision_call_tools, make_agent


@pytest.mark.asyncio
async def test_greeting_without_user_input(
    sample_config: AgentConfig,
    respond_llm: ScriptedLLM,
) -> None:
    agent = make_agent(sample_config, respond_llm)
    session = agent.create_session()
    result = await agent.step(session, user_input=None)
    assert result.kind == "respond"
    assert result.message == sample_config.greeting
    assert session.greeting_sent is True
    assert respond_llm.calls == []  # greeting short-circuits LLM


@pytest.mark.asyncio
async def test_respond_only_turn(
    sample_config: AgentConfig,
) -> None:
    llm = ScriptedLLM([AgentDecision(kind="respond", message="Sure thing.")])
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="Hi")
    assert result.kind == "respond"
    assert result.message == "Sure thing."
    assert result.rounds_used == 1


@pytest.mark.asyncio
async def test_single_tool_call_then_respond(
    sample_config: AgentConfig,
) -> None:
    llm = ScriptedLLM(
        [
            decision_call_tools(("calculator", {"expression": "2 + 2"})),
            AgentDecision(kind="respond", message="The answer is 4."),
        ]
    )
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="What is 2+2?")
    assert result.kind == "respond"
    assert result.message == "The answer is 4."
    assert result.rounds_used == 2
    assert len(result.tool_results) == 1
    assert result.tool_results[0]["success"] is True
    assert result.tool_results[0]["output"] == "4.0"


@pytest.mark.asyncio
async def test_multi_round_tool_loop(
    sample_config: AgentConfig,
) -> None:
    llm = ScriptedLLM(
        [
            decision_call_tools(("note", {"action": "write", "text": "alpha"})),
            decision_call_tools(("note", {"action": "read"})),
            AgentDecision(kind="respond", message="Stored note is alpha."),
        ]
    )
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="Remember alpha then read it")
    assert result.kind == "respond"
    assert result.rounds_used == 3
    assert len(result.tool_results) == 2
    assert result.tool_results[1]["output"] == "alpha"


@pytest.mark.asyncio
async def test_max_tool_rounds_stop(
    sample_config: AgentConfig,
) -> None:
    sample_config.max_tool_rounds = 2
    llm = ScriptedLLM(
        [
            decision_call_tools(("calculator", {"expression": "1 + 1"})),
            decision_call_tools(("calculator", {"expression": "2 + 2"})),
            # Would be a third decision, but loop must stop at 2
            AgentDecision(kind="respond", message="should not reach"),
        ]
    )
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="Keep calculating")
    assert result.kind == "respond"
    assert result.rounds_used == 2
    assert "maximum number of tool rounds" in result.message.lower()
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_unknown_tool_graceful(
    sample_config: AgentConfig,
) -> None:
    llm = ScriptedLLM(
        [
            decision_call_tools(("does_not_exist", {"x": 1})),
            AgentDecision(
                kind="respond",
                message="That tool is unavailable; I cannot help that way.",
            ),
        ]
    )
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="Use a missing tool")
    assert result.kind == "respond"
    assert result.tool_results[0]["success"] is False
    assert "Unknown tool" in (result.tool_results[0]["error"] or "")


@pytest.mark.asyncio
async def test_done_kind(
    sample_config: AgentConfig,
) -> None:
    llm = ScriptedLLM([AgentDecision(kind="done", message="Goodbye!")])
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="bye")
    assert result.kind == "done"
    assert session.done is True


@pytest.mark.asyncio
async def test_empty_tool_calls_list(
    sample_config: AgentConfig,
) -> None:
    llm = ScriptedLLM([AgentDecision(kind="call_tools", message="", tool_calls=[])])
    agent = make_agent(sample_config, llm)
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="call nothing")
    assert result.kind == "respond"
    assert "no tool calls" in result.message.lower()


@pytest.mark.asyncio
async def test_compaction_runs_before_decide(
    sample_config: AgentConfig,
) -> None:
    from ai_agent.domain.models import CompactionConfig, Message
    from ai_agent.harness.compaction import SUMMARY_PREFIX, ContextSummary

    sample_config.compaction = CompactionConfig(
        enabled=True,
        max_context_chars=100,
        keep_recent_messages=1,
        max_summary_chars=400,
    )
    llm = ScriptedLLM(
        [
            ContextSummary(summary="Earlier: long research about orchards."),
            AgentDecision(kind="respond", message="Done."),
        ]
    )
    agent = make_agent(sample_config, llm)
    session = ConversationState(
        greeting_sent=True,
        messages=[
            Message(role="user", content="old " * 40),
            Message(role="assistant", content="old " * 40),
        ],
    )
    result = await agent.step(session, user_input="wrap up")
    assert result.kind == "respond"
    assert result.message == "Done."
    assert len(llm.calls) == 2  # summary + decide
    decide_messages = llm.calls[1]
    assert any(SUMMARY_PREFIX in m.get("content", "") for m in decide_messages)
    assert session.context_summary is not None
    # Full history still grows (system + prior + new user + assistant respond)
    assert len(session.messages) >= 4
