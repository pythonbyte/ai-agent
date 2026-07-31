"""httpx-backed HTTP fetcher with scheme and size limits."""

from __future__ import annotations

import httpx

from ai_agent.application.url_safety import HttpFetchError, assert_allowed_url

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_BYTES = 100_000

__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "HttpFetchError",
    "HttpxFetcher",
    "assert_allowed_url",
]


class HttpxFetcher:
    """Infrastructure adapter implementing HttpFetcher."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def get_text(self, url: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
        assert_allowed_url(url)
        limit = max(1, max_bytes)

        if self._client is not None:
            response = await self._client.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            return _decode_truncated(response.content, limit)

        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return _decode_truncated(response.content, limit)


def _decode_truncated(raw: bytes, max_bytes: int) -> str:
    chunk = raw[:max_bytes]
    if b"\x00" in chunk:
        raise HttpFetchError("Response appears to be binary")
    text = chunk.decode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        return text + f"\n...[truncated at {max_bytes} bytes]"
    return text
