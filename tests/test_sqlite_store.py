"""Tests for SQLite session/memory store and memory tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.domain.models import AgentConfig, AgentDecision
from ai_agent.domain.state import ConversationState
from ai_agent.infrastructure.sqlite_store import SqliteStore
from ai_agent.orchestration.runtime import AgentRuntime
from ai_agent.tools.memory import MemoryTool
from tests.conftest import ScriptedLLM, make_agent


def test_sqlite_session_roundtrip(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "state.db")
    state = ConversationState()
    state.add_message("user", "hello")
    state.add_message("assistant", "hi")
    store.save("a1", state)

    loaded = store.load("a1")
    assert loaded is not None
    assert len(loaded.messages) == 2
    assert loaded.messages[0].content == "hello"
    assert store.load("missing") is None


def test_sqlite_memory_crud(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "state.db")
    store.put("user.name", "Ada")
    store.put("user.city", "London")
    assert store.get("user.name") == "Ada"
    assert store.list_keys("user.") == ["user.city", "user.name"]
    assert store.get("missing") is None


@pytest.mark.asyncio
async def test_memory_tool(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "state.db")
    tool = MemoryTool(store)
    written = await tool.execute(
        {"action": "write", "key": "pref", "value": "dark"},
    )
    assert written.success is True
    read = await tool.execute({"action": "read", "key": "pref"})
    assert read.output == "dark"
    listed = await tool.execute({"action": "list"})
    assert "pref" in listed.output


@pytest.mark.asyncio
async def test_runtime_reloads_session(
    sample_config: AgentConfig,
    tmp_path: Path,
) -> None:
    store = SqliteStore(tmp_path / "state.db")
    llm = ScriptedLLM(
        [
            AgentDecision(kind="respond", message="saved"),
        ]
    )
    agent = make_agent(sample_config, llm)
    runtime = AgentRuntime(on_agent_output=lambda *_: None, session_store=store)
    runtime.register("a1", agent)
    task = await runtime.start_agent("a1")
    import asyncio

    await asyncio.sleep(0.05)
    await runtime.send_message("a1", "hello")
    await asyncio.sleep(0.1)
    await runtime.stop_agent("a1")
    await asyncio.wait_for(task, timeout=2.0)

    loaded = store.load("a1")
    assert loaded is not None
    assert any(m.content == "hello" for m in loaded.messages)

    runtime2 = AgentRuntime(on_agent_output=lambda *_: None, session_store=store)
    agent2 = make_agent(sample_config, ScriptedLLM([]))
    runtime2.register("a1", agent2)
    session = runtime2.get_session("a1")
    assert any(m.content == "hello" for m in session.messages)
