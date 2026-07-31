"""Retrieve tool — semantic search over an indexed corpus."""

from __future__ import annotations

from typing import Any

from ai_agent.adapters.chroma_retriever import format_chunks
from ai_agent.domain.ports import Retriever
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class RetrieveTool(BaseTool):
    """Query the knowledge base and return ranked text chunks."""

    def __init__(self, retriever: Retriever, *, default_top_k: int = 5) -> None:
        super().__init__(
            name="retrieve",
            description=(
                "Semantic search over indexed docs. "
                "Use when answering questions about project documentation."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Natural language search query",
                    required=True,
                ),
                ToolParameter(
                    name="top_k",
                    type="integer",
                    description="Max chunks to return (default 5)",
                    required=False,
                ),
            ],
        )
        self._retriever = retriever
        self._default_top_k = default_top_k

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"]).strip()
        if not query:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="query must be non-empty",
            )
        top_k = arguments.get("top_k", self._default_top_k)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            top_k = self._default_top_k
        try:
            chunks = await self._retriever.retrieve(query, top_k=top_k)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=format_chunks(chunks),
        )
