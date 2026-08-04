"""Tests for spawn budgets."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.domain.models import AgentConfig, AgentDecision
from ai_agent.domain.platform import SpawnBudget
from ai_agent.orchestration.factory import AgentFactory
from ai_agent.orchestration.runtime import AgentRuntime
from tests.conftest import ScriptedLLM, make_agent


class _FixedFactory:
    """Minimal factory stand-in for spawn budget tests."""

    def __init__(self, make) -> None:
        self._make = make

    def create(self, role: str, *, agent_id: str, messenger_sender_id: str | None = None):
        return self._make()


@pytest.mark.asyncio
async def test_spawn_depth_limit(sample_config: AgentConfig) -> None:
    parent = make_agent(sample_config, ScriptedLLM([]))

    def make_child():
        return make_agent(
            sample_config,
            ScriptedLLM(
                [
                    AgentDecision(kind="respond", message="child ok"),
                ]
            ),
        )

    runtime = AgentRuntime(
        on_agent_output=lambda *_: None,
        spawn_budget=SpawnBudget(max_depth=1, max_children=4),
    )
    runtime.set_factory(_FixedFactory(make_child))  # type: ignore[arg-type]
    runtime.register("parent", parent)
    await runtime.start_agent("parent")

    reply = await runtime.spawn("researcher", "hi", sender="parent", depth=0)
    assert reply == "child ok"

    denied = await runtime.spawn("researcher", "hi", sender="parent", depth=1)
    assert "depth limit" in denied
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_spawn_child_limit(sample_config: AgentConfig) -> None:
    parent = make_agent(sample_config, ScriptedLLM([]))
    runtime = AgentRuntime(
        on_agent_output=lambda *_: None,
        spawn_budget=SpawnBudget(max_depth=2, max_children=1),
    )
    runtime.set_factory(_FixedFactory(lambda: make_agent(sample_config, ScriptedLLM([]))))  # type: ignore[arg-type]
    runtime.register("parent", parent)
    runtime._children["parent"].append("already")  # noqa: SLF001
    denied = await runtime.spawn("researcher", "hi", sender="parent", depth=0)
    assert "child limit" in denied


def test_factory_role_path(tmp_path: Path) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "engineer.yaml").write_text(
        "model: openai/gpt-4o-mini\n"
        "system_prompt: x\n"
        "max_tool_rounds: 2\n"
        "personality: {tone: neutral, style: concise}\n"
        "greeting: hi\n"
        "tools: [calculator]\n",
        encoding="utf-8",
    )
    factory = AgentFactory(agents_dir=agents)
    assert factory.role_path("engineer").name == "engineer.yaml"
    with pytest.raises(FileNotFoundError):
        factory.role_path("missing")
