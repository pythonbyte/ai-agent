"""Tests for research brief use-case."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.application.brief import (
    render_brief_markdown,
    run_research_brief,
    slugify,
)
from ai_agent.domain.models import AgentConfig, AgentDecision, Personality, StepResult
from ai_agent.infrastructure.approval import AutoApprovalGate
from ai_agent.tools import build_default_registry
from tests.conftest import ScriptedLLM, decision_call_tools, make_agent


def test_slugify() -> None:
    assert slugify("Agent Harness!") == "agent-harness"
    assert slugify("   ") == "brief"


def test_render_brief_markdown() -> None:
    result = StepResult(
        message="## Summary\nHello\n## Sources\n- https://x.com",
        kind="respond",
        tool_results=[{"tool_name": "web_search", "success": True}],
        rounds_used=2,
    )
    text = render_brief_markdown("topic", result)
    assert "# Research brief: topic" in text
    assert "## Sources" in text
    assert "web_search" in text


@pytest.mark.asyncio
async def test_run_research_brief_writes_file(tmp_path: Path) -> None:
    config = AgentConfig(
        model="openai/gpt-4o-mini",
        system_prompt="Research.",
        max_tool_rounds=5,
        personality=Personality(),
        tools=["web_search"],
        greeting="hi",
    )
    llm = ScriptedLLM(
        [
            decision_call_tools(("web_search", {"query": "agent harness"})),
            AgentDecision(
                kind="respond",
                message=(
                    "## Summary\nHarness wraps the model.\n"
                    "## Key findings\n- Tools and memory.\n"
                    "## Sources\n- https://example.com/harness\n"
                    "## Open questions\n- How far can self-heal go?"
                ),
            ),
        ]
    )
    from ai_agent.domain.ports import SearchHit

    class FakeSearcher:
        async def search(self, query: str, *, max_results: int = 5) -> list[SearchHit]:
            return [
                SearchHit(
                    title="Harness",
                    url="https://example.com/harness",
                    snippet="Agent = Model + Harness",
                )
            ]

    registry = build_default_registry(web_searcher=FakeSearcher())
    # Only web_search selected via make_agent select
    agent = make_agent(config, llm, registry=registry)
    out = tmp_path / "briefs"
    path = await run_research_brief("agent harness", agent=agent, output_dir=out)
    assert path.is_file()
    body = path.read_text(encoding="utf-8")
    assert "## Sources" in body
    assert "https://example.com/harness" in body


@pytest.mark.asyncio
async def test_run_research_brief_approval_denied(tmp_path: Path) -> None:
    config = AgentConfig(
        model="openai/gpt-4o-mini",
        system_prompt="Research.",
        tools=[],
        greeting="hi",
    )
    llm = ScriptedLLM(
        [AgentDecision(kind="respond", message="## Summary\nx\n## Sources\n- none")]
    )
    agent = make_agent(config, llm)
    gate = AutoApprovalGate(approve=False)
    with pytest.raises(PermissionError):
        await run_research_brief(
            "topic",
            agent=agent,
            output_dir=tmp_path,
            approval_gate=gate,
            require_approval=True,
        )
