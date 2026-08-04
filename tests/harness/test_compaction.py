"""Tests for context compaction pure helpers and SummarizingCompactor."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_agent.domain.models import CompactionConfig, Message
from ai_agent.domain.state import ConversationState
from ai_agent.harness.compaction import (
    SUMMARY_PREFIX,
    ContextSummary,
    SummarizingCompactor,
    build_wire_messages,
    clamp_summary,
    deterministic_summary,
    estimate_chars,
    needs_compaction,
    split_messages,
)


def test_estimate_chars() -> None:
    assert estimate_chars([{"role": "user", "content": "hi"}]) == len("user") + len("hi")


def test_needs_compaction_guardrails() -> None:
    assert needs_compaction(enabled=False, char_count=99_999, max_context_chars=100) is False
    assert needs_compaction(enabled=True, char_count=50, max_context_chars=100) is False
    assert needs_compaction(enabled=True, char_count=101, max_context_chars=100) is True
    assert needs_compaction(enabled=True, char_count=100, max_context_chars=0) is False


def test_split_messages_keeps_system_and_recent() -> None:
    messages = [
        Message(role="system", content="sys"),
        Message(role="user", content="u1"),
        Message(role="assistant", content="a1"),
        Message(role="user", content="u2"),
        Message(role="assistant", content="a2"),
    ]
    system, old, recent = split_messages(messages, keep_recent=2)
    assert system is not None and system.content == "sys"
    assert [m.content for m in old] == ["u1", "a1"]
    assert [m.content for m in recent] == ["u2", "a2"]


def test_split_messages_short_history_has_empty_old() -> None:
    messages = [
        Message(role="system", content="sys"),
        Message(role="user", content="only"),
    ]
    system, old, recent = split_messages(messages, keep_recent=5)
    assert system is not None
    assert old == []
    assert len(recent) == 1


def test_split_messages_rejects_bad_keep_recent() -> None:
    with pytest.raises(ValueError):
        split_messages([], keep_recent=0)


def test_clamp_summary() -> None:
    assert clamp_summary("  hello  ", max_chars=100) == "hello"
    assert clamp_summary("", max_chars=100) == "(no earlier context)"
    clamped = clamp_summary("x" * 50, max_chars=20)
    assert len(clamped) <= 20
    assert clamped.endswith("...[truncated]")
    with pytest.raises(ValueError):
        clamp_summary("hi", max_chars=0)


def test_deterministic_summary_includes_roles() -> None:
    text = deterministic_summary(
        [Message(role="user", content="find apple price"), Message(role="tool", content="ok", tool_name="web_search")],
        max_chars=500,
    )
    assert "user:" in text
    assert "web_search:" in text


def test_build_wire_messages_maps_tool_role() -> None:
    wire = build_wire_messages(
        system=Message(role="system", content="sys"),
        summary="earlier stuff",
        recent=[Message(role="tool", content="42", tool_name="calculator")],
    )
    assert wire[0] == {"role": "system", "content": "sys"}
    assert wire[1]["content"].startswith(SUMMARY_PREFIX)
    assert "Observation from calculator" in wire[2]["content"]


class _Scripted:
    def __init__(self, items: list[BaseModel]) -> None:
        self.items = list(items)
        self.calls = 0

    async def complete(self, messages: list[dict[str, str]], output_model: type[BaseModel]) -> BaseModel:
        self.calls += 1
        item = self.items.pop(0)
        return output_model.model_validate(item.model_dump())


@pytest.mark.asyncio
async def test_summarizing_compactor_passthrough_under_budget() -> None:
    llm = _Scripted([])
    packer = SummarizingCompactor(llm)
    state = ConversationState(
        messages=[
            Message(role="system", content="sys"),
            Message(role="user", content="hi"),
        ]
    )
    packed = await packer.pack(
        state,
        budget=CompactionConfig(enabled=True, max_context_chars=10_000, keep_recent_messages=4),
    )
    assert packed.compacted is False
    assert llm.calls == 0
    assert packed.messages[-1]["content"] == "hi"
    assert len(state.messages) == 2  # history untouched


@pytest.mark.asyncio
async def test_summarizing_compactor_summarizes_over_budget() -> None:
    llm = _Scripted([ContextSummary(summary="User asked about apples; search returned $100.")])
    packer = SummarizingCompactor(llm)
    old_blob = "x" * 200
    state = ConversationState(
        messages=[
            Message(role="system", content="sys"),
            Message(role="user", content=old_blob),
            Message(role="assistant", content=old_blob),
            Message(role="user", content="recent question"),
            Message(role="assistant", content="recent answer"),
        ]
    )
    packed = await packer.pack(
        state,
        budget=CompactionConfig(
            enabled=True,
            max_context_chars=100,
            keep_recent_messages=2,
            max_summary_chars=500,
        ),
    )
    assert packed.compacted is True
    assert llm.calls == 1
    assert packed.summary is not None
    assert "apples" in packed.summary
    assert state.context_summary == packed.summary
    assert any(SUMMARY_PREFIX in m["content"] for m in packed.messages)
    assert packed.messages[-1]["content"] == "recent answer"
    # Full history preserved
    assert len(state.messages) == 5


@pytest.mark.asyncio
async def test_summarizing_compactor_falls_back_when_llm_fails() -> None:
    class Boom:
        async def complete(self, messages: list[dict[str, str]], output_model: type[BaseModel]) -> BaseModel:
            raise RuntimeError("llm down")

    packer = SummarizingCompactor(Boom())  # type: ignore[arg-type]
    state = ConversationState(
        messages=[
            Message(role="system", content="sys"),
            Message(role="user", content="old-a" * 40),
            Message(role="assistant", content="old-b" * 40),
            Message(role="user", content="now"),
        ]
    )
    packed = await packer.pack(
        state,
        budget=CompactionConfig(enabled=True, max_context_chars=100, keep_recent_messages=1),
    )
    assert packed.compacted is True
    assert packed.summary is not None
    assert "old-a" in packed.summary or "user:" in packed.summary
