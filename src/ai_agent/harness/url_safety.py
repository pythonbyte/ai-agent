"""Pure URL safety checks for http_get."""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class HttpFetchError(ValueError):
    """Raised when a URL cannot be fetched safely."""


def assert_allowed_url(url: str) -> None:
    """Reject non-http(s) URLs early (pure, mutation-test friendly)."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise HttpFetchError(f"Only http/https URLs are allowed, got scheme={parsed.scheme!r}")
    if not parsed.netloc:
        raise HttpFetchError("URL must include a host")
