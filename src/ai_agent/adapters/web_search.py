"""DuckDuckGo web search adapter (no API key)."""

from __future__ import annotations

import asyncio
import logging

from ai_agent.domain.ports import SearchHit

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 5


class DuckDuckGoSearcher:
    """
    Infrastructure adapter implementing WebSearcher via the ``ddgs`` package.

    Runs the sync client in a worker thread so the agent loop stays async.
    """

    def __init__(self, *, max_results: int = DEFAULT_MAX_RESULTS) -> None:
        self.max_results = max(1, max_results)

    async def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[SearchHit]:
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("query must be non-empty")
        limit = max(1, max_results)
        return await asyncio.to_thread(self._search_sync, cleaned, limit)

    def _search_sync(self, query: str, max_results: int) -> list[SearchHit]:
        try:
            from ddgs import DDGS
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "ddgs is required for web_search. Install project dependencies."
            ) from exc

        hits: list[SearchHit] = []
        with DDGS() as client:
            raw_results = list(client.text(query, max_results=max_results))
        for item in raw_results:
            title = str(item.get("title") or "")
            url = str(item.get("href") or item.get("link") or "")
            snippet = str(item.get("body") or item.get("snippet") or "")
            if not title and not url:
                continue
            hits.append(SearchHit(title=title, url=url, snippet=snippet))
        logger.debug("duckduckgo_search query=%r hits=%s", query, len(hits))
        return hits
