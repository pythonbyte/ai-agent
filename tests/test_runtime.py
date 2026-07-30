"""Tests for AgentRuntime orchestration."""

from __future__ import annotations

import asyncio

import pytest

from ai_agent.domain.models import AgentConfig, AgentDecision, StepResult
from ai_agent.orchestration.runtime import AgentRuntime, MessageType, RuntimeMessage
from tests.conftest import ScriptedLLM, make_agent


@pytest.mark.asyncio
async def test_register_and_get_session(sample_config: AgentConfig) -> None:
    llm = ScriptedLLM([AgentDecision(kind="respond", message="hi")])
    agent = make_agent(sample_config, llm)
    runtime = AgentRuntime(on_agent_output=lambda *_: None)
    runtime.register("a1", agent)
    session = runtime.get_session("a1")
    assert session.done is False
    with pytest.raises(ValueError):
        runtime.register("a1", agent)


@pytest.mark.asyncio
async def test_send_and_stop(sample_config: AgentConfig) -> None:
    outputs: list[StepResult] = []

    def capture(_agent_id: str, result: StepResult) -> None:
        outputs.append(result)

    llm = ScriptedLLM(
        [
            AgentDecision(kind="respond", message="got it"),
            AgentDecision(kind="done", message="bye"),
        ]
    )
    agent = make_agent(sample_config, llm)
    runtime = AgentRuntime(on_agent_output=capture)
    runtime.register("a1", agent)
    task = await runtime.start_agent("a1")

    # Wait for greeting
    await asyncio.sleep(0.05)
    assert outputs
    assert outputs[0].message == sample_config.greeting

    await runtime.send_message("a1", "hello")
    await asyncio.sleep(0.1)
    await runtime.send_message("a1", "bye")
    await asyncio.wait_for(task, timeout=2.0)

    assert any(o.kind == "done" for o in outputs)
    assert runtime.get_session("a1").done is True


@pytest.mark.asyncio
async def test_shutdown_message(sample_config: AgentConfig) -> None:
    llm = ScriptedLLM([])  # no further LLM calls after greeting
    agent = make_agent(sample_config, llm)
    runtime = AgentRuntime(on_agent_output=lambda *_: None)
    runtime.register("a1", agent)
    task = await runtime.start_agent("a1")
    await asyncio.sleep(0.05)
    await runtime.stop_agent("a1")
    await asyncio.wait_for(task, timeout=2.0)
    assert runtime._contexts["a1"].active is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_runtime_message_types() -> None:
    msg = RuntimeMessage(
        sender="runtime",
        recipient="a1",
        payload=None,
        message_type=MessageType.SHUTDOWN,
    )
    assert msg.message_type == MessageType.SHUTDOWN
