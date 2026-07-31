"""Tests for web_search tool."""

from __future__ import annotations

import pytest

from ai_agent.domain.ports import SearchHit
from ai_agent.tools.web_search import WebSearchTool


class FakeSearcher:
    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self.hits = hits or []
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchHit]:
        self.calls.append((query, max_results))
        return self.hits[:max_results]


@pytest.mark.asyncio
async def test_web_search_success() -> None:
    searcher = FakeSearcher(
        [
            SearchHit(
                title="Agent Harness Explained",
                url="https://example.com/harness",
                snippet="An agent harness orchestrates tools and loops.",
            )
        ]
    )
    tool = WebSearchTool(searcher)
    result = await tool.execute({"query": "agent harness"})
    assert result.success is True
    assert "Agent Harness" in result.output
    assert searcher.calls[0][0] == "agent harness"


@pytest.mark.asyncio
async def test_web_search_empty_query() -> None:
    tool = WebSearchTool(FakeSearcher())
    result = await tool.execute({"query": "   "})
    assert result.success is False


@pytest.mark.asyncio
async def test_web_search_no_hits() -> None:
    tool = WebSearchTool(FakeSearcher([]))
    result = await tool.execute({"query": "zzzzunlikely"})
    assert result.success is True
    assert result.output == "(no results)"
