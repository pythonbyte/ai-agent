"""Tests for harness circuit-breaker on repeated tool failures."""

from __future__ import annotations

import pytest

from ai_agent.domain.models import AgentConfig
from ai_agent.domain.state import ConversationState
from ai_agent.domain.tool import BaseTool, ToolResult
from ai_agent.harness.agent import Agent
from ai_agent.harness.registry import ToolRegistry
from tests.conftest import ScriptedLLM, decision_call_tools


class _AlwaysFailTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(name="apply_patch", description="fail", parameters=[])

    async def execute(self, arguments: dict[str, object]) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=False,
            output="",
            error="context mismatch",
        )


@pytest.mark.asyncio
async def test_apply_patch_circuit_breaker_stops(sample_config: AgentConfig) -> None:
    sample_config.tools = ["apply_patch"]
    sample_config.max_tool_rounds = 10
    registry = ToolRegistry()
    registry.register(_AlwaysFailTool())
    llm = ScriptedLLM(
        [
            decision_call_tools(("apply_patch", {"patch": "x"})),
            decision_call_tools(("apply_patch", {"patch": "x"})),
            decision_call_tools(("apply_patch", {"patch": "x"})),
            decision_call_tools(("apply_patch", {"patch": "x"})),
            decision_call_tools(("apply_patch", {"patch": "x"})),
        ]
    )
    agent = Agent(config=sample_config, llm=llm, registry=registry, agent_id="t")
    session = ConversationState(greeting_sent=True)
    result = await agent.step(session, user_input="patch it")
    assert result.kind == "respond"
    assert "5 times" in result.message
    assert len(result.tool_results) == 5
