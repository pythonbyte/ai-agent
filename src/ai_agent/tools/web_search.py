"""web_search tool — public web search via a WebSearcher port."""

from __future__ import annotations

import json
from typing import Any

from ai_agent.domain.ports import WebSearcher
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class WebSearchTool(BaseTool):
    """Search the public web (DuckDuckGo) for a query."""

    def __init__(self, searcher: WebSearcher, *, default_max_results: int = 5) -> None:
        super().__init__(
            name="web_search",
            description=(
                "Search the public web for a query and return titles, URLs, and snippets. "
                "Use for topics not covered by local docs (e.g. industry articles, definitions). "
                "Follow up with http_get on a promising URL when you need full page text."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True,
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Max results to return (default 5)",
                    required=False,
                ),
            ],
        )
        self._searcher = searcher
        self._default_max_results = default_max_results

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"]).strip()
        if not query:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="query must be non-empty",
            )
        max_results = arguments.get("max_results", self._default_max_results)
        if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
            max_results = self._default_max_results
        try:
            hits = await self._searcher.search(query, max_results=max_results)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        if not hits:
            return ToolResult(
                tool_name=self.name,
                success=True,
                output="(no results)",
            )
        payload = [
            {"title": hit.title, "url": hit.url, "snippet": hit.snippet} for hit in hits
        ]
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=json.dumps(payload, indent=2),
        )
