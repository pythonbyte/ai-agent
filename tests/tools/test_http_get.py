"""Tests for http_get tool and URL safety helpers."""

from __future__ import annotations

import pytest

from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult
from ai_agent.harness.registry import ToolRegistry
from ai_agent.harness.url_safety import HttpFetchError, assert_allowed_url
from ai_agent.tools.http_get import HttpGetTool


class FakeFetcher:
    def __init__(self, body: str = "hello") -> None:
        self.body = body
        self.calls: list[tuple[str, int]] = []

    async def get_text(self, url: str, *, max_bytes: int) -> str:
        self.calls.append((url, max_bytes))
        return self.body[:max_bytes]


class SpyTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="spy",
            description="spy",
            parameters=[
                ToolParameter(name="text", type="string", description="t", required=True),
            ],
        )
        self.executed = False

    async def execute(self, arguments: dict[str, object]) -> ToolResult:
        self.executed = True
        return ToolResult(tool_name=self.name, success=True, output="ok")


class TestAssertAllowedUrl:
    def test_https_ok(self) -> None:
        assert_allowed_url("https://example.com/a")

    def test_http_ok(self) -> None:
        assert_allowed_url("http://example.com/a")

    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(HttpFetchError):
            assert_allowed_url("file:///etc/passwd")

    def test_rejects_ftp(self) -> None:
        with pytest.raises(HttpFetchError, match="http/https"):
            assert_allowed_url("ftp://example.com")

    def test_rejects_missing_host(self) -> None:
        with pytest.raises(HttpFetchError):
            assert_allowed_url("https:///nohost")

    def test_rejects_empty_scheme(self) -> None:
        with pytest.raises(HttpFetchError):
            assert_allowed_url("example.com/path")


@pytest.mark.asyncio
async def test_http_get_success() -> None:
    fetcher = FakeFetcher("body")
    tool = HttpGetTool(fetcher)
    result = await tool.execute({"url": "https://example.com"})
    assert result.success is True
    assert result.output == "body"
    assert fetcher.calls[0][0] == "https://example.com"


@pytest.mark.asyncio
async def test_http_get_rejects_bad_scheme() -> None:
    tool = HttpGetTool(FakeFetcher())
    result = await tool.execute({"url": "ftp://example.com"})
    assert result.success is False
    assert "http/https" in (result.error or "")


@pytest.mark.asyncio
async def test_registry_validation_skips_execute() -> None:
    spy = SpyTool()
    registry = ToolRegistry()
    registry.register(spy)
    result = await registry.execute("spy", {})
    assert result.success is False
    assert "Missing required" in (result.error or "")
    assert spy.executed is False
