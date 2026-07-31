"""Tests for multi-agent ask / message_agent handoff."""

from __future__ import annotations

import asyncio

import pytest

from ai_agent.domain.models import AgentConfig, AgentDecision, Personality
from ai_agent.harness.registry import ToolRegistry
from ai_agent.orchestration.runtime import AgentRuntime
from ai_agent.tools.message_agent import MessageAgentTool
from tests.conftest import ScriptedLLM, decision_call_tools, make_agent


@pytest.mark.asyncio
async def test_runtime_ask_agent(sample_config: AgentConfig) -> None:
    researcher_llm = ScriptedLLM([AgentDecision(kind="respond", message="Research says 42")])
    researcher = make_agent(sample_config, researcher_llm)

    runtime = AgentRuntime(on_agent_output=lambda *_: None, ask_timeout_seconds=2.0)
    runtime.register("researcher", researcher)
    await runtime.start_agent("researcher")
    await asyncio.sleep(0.05)

    reply = await runtime.ask(
        "researcher",
        "What is the answer?",
        sender="coordinator",
    )
    assert reply == "Research says 42"
    await runtime.stop_agent("researcher")


@pytest.mark.asyncio
async def test_runtime_ask_rejects_self() -> None:
    runtime = AgentRuntime(on_agent_output=lambda *_: None)
    reply = await runtime.ask("a", "hi", sender="a")
    assert reply.startswith("Error:")


@pytest.mark.asyncio
async def test_message_agent_tool_and_coordinator_loop(
    sample_config: AgentConfig,
) -> None:
    researcher_llm = ScriptedLLM(
        [AgentDecision(kind="respond", message="Brief: use Clean Architecture.")]
    )
    researcher = make_agent(sample_config, researcher_llm)

    runtime = AgentRuntime(on_agent_output=lambda *_: None, ask_timeout_seconds=2.0)
    runtime.register("researcher", researcher)
    await runtime.start_agent("researcher")
    await asyncio.sleep(0.05)

    registry = ToolRegistry()
    registry.register(MessageAgentTool(runtime, sender_id="coordinator"))

    coord_config = AgentConfig(
        model=sample_config.model,
        system_prompt="You coordinate.",
        max_tool_rounds=5,
        personality=Personality(),
        tools=["message_agent"],
        greeting="Coordinator ready.",
    )
    coord_llm = ScriptedLLM(
        [
            decision_call_tools(
                ("message_agent", {"agent_id": "researcher", "message": "Summarize arch"})
            ),
            AgentDecision(
                kind="respond",
                message="The researcher recommends Clean Architecture.",
            ),
        ]
    )
    coordinator = make_agent(coord_config, coord_llm, registry=registry)
    runtime.register("coordinator", coordinator)

    session = coordinator.create_session()
    result = await coordinator.step(session=session, user_input="Explain the architecture")
    assert result.kind == "respond"
    assert "Clean Architecture" in result.message
    assert result.tool_results[0]["success"] is True

    await runtime.shutdown()
