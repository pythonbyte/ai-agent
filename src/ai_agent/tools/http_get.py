"""HTTP GET tool — fetches URL text via an HttpFetcher port."""

from __future__ import annotations

from typing import Any

from ai_agent.application.url_safety import assert_allowed_url
from ai_agent.domain.ports import HttpFetcher
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult
from ai_agent.infrastructure.http_fetcher import DEFAULT_MAX_BYTES


class HttpGetTool(BaseTool):
    """Fetch the text body of an http(s) URL."""

    def __init__(self, fetcher: HttpFetcher, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        super().__init__(
            name="http_get",
            description=(
                "Fetch text content from an http or https URL. "
                "Use for public web pages or APIs that return text."
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="Full http(s) URL to fetch",
                    required=True,
                ),
            ],
        )
        self._fetcher = fetcher
        self._max_bytes = max_bytes

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        url = str(arguments["url"])
        try:
            assert_allowed_url(url)
            body = await self._fetcher.get_text(url, max_bytes=self._max_bytes)
        except Exception as exc:  # noqa: BLE001 — surface to LLM
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        return ToolResult(tool_name=self.name, success=True, output=body)
