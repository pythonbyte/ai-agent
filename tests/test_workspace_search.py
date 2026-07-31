"""Tests for sandboxed workspace search/read."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.adapters.workspace_fs import WorkspaceFS, is_within_root
from ai_agent.tools.workspace_search import WorkspaceSearchTool


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "readme.md").write_text("hello agent kit\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ship it')\n", encoding="utf-8")
    return tmp_path


class TestIsWithinRoot:
    def test_inside(self, workspace: Path) -> None:
        assert is_within_root(workspace, workspace / "readme.md") is True

    def test_escape(self, workspace: Path) -> None:
        assert is_within_root(workspace, workspace / ".." / "outside") is False


class TestWorkspaceFS:
    def test_read_text(self, workspace: Path) -> None:
        fs = WorkspaceFS(workspace)
        assert "hello" in fs.read_text("readme.md")

    def test_path_escape_rejected(self, workspace: Path) -> None:
        fs = WorkspaceFS(workspace)
        with pytest.raises(ValueError, match="escapes"):
            fs.resolve_safe("../secret")

    def test_search(self, workspace: Path) -> None:
        fs = WorkspaceFS(workspace)
        hits = fs.search("ship", glob_pattern="**/*.py", max_results=5)
        assert len(hits) == 1
        assert hits[0][0].endswith("main.py")


@pytest.mark.asyncio
async def test_workspace_search_tool(workspace: Path) -> None:
    tool = WorkspaceSearchTool(WorkspaceFS(workspace))
    searched = await tool.execute({"action": "search", "query": "agent"})
    assert searched.success is True
    assert "readme.md" in searched.output

    read = await tool.execute({"action": "read", "path": "readme.md"})
    assert read.success is True
    assert "hello" in read.output


@pytest.mark.asyncio
async def test_workspace_search_escape(workspace: Path) -> None:
    tool = WorkspaceSearchTool(WorkspaceFS(workspace))
    result = await tool.execute({"action": "read", "path": "../outside.txt"})
    assert result.success is False
    assert "escapes" in (result.error or "")
