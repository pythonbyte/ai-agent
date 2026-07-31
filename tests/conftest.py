"""Shared pytest fixtures."""

from __future__ import annotations

from typing import Any

import pytest

from ai_agent.domain.models import AgentConfig, AgentDecision, Personality, ToolCallRequest
from ai_agent.domain.state import ConversationState
from ai_agent.harness.agent import Agent
from ai_agent.harness.registry import ToolRegistry
from ai_agent.tools import build_default_registry


@pytest.fixture
def sample_config() -> AgentConfig:
    return AgentConfig(
        model="openai/gpt-4o-mini",
        system_prompt="You are a test agent. Use tools when helpful.",
        max_tool_rounds=5,
        personality=Personality(tone="neutral", style="concise"),
        tools=["calculator", "current_time", "note"],
        greeting="Hello from tests.",
    )


@pytest.fixture
def registry() -> ToolRegistry:
    return build_default_registry()


@pytest.fixture
def session() -> ConversationState:
    return ConversationState()


class ScriptedLLM:
    """Deterministic LLM stand-in that returns a scripted sequence of decisions."""

    def __init__(self, decisions: list[AgentDecision]) -> None:
        self._decisions = list(decisions)
        self.calls: list[list[dict[str, str]]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        output_model: type[Any],
    ) -> Any:
        self.calls.append(messages)
        if not self._decisions:
            raise AssertionError("ScriptedLLM has no more decisions")
        decision = self._decisions.pop(0)
        return output_model.model_validate(decision.model_dump())


@pytest.fixture
def respond_llm() -> ScriptedLLM:
    return ScriptedLLM([AgentDecision(kind="respond", message="Hello, human.")])


def make_agent(
    config: AgentConfig,
    llm: ScriptedLLM,
    registry: ToolRegistry | None = None,
) -> Agent:
    reg = registry or build_default_registry()
    selected = reg.select(config.tools) if config.tools else reg
    return Agent(config=config, llm=llm, registry=selected, agent_id="test-agent")


def decision_call_tools(*calls: tuple[str, dict[str, object]]) -> AgentDecision:
    return AgentDecision(
        kind="call_tools",
        message="",
        tool_calls=[ToolCallRequest(name=name, arguments=dict(args)) for name, args in calls],
    )
