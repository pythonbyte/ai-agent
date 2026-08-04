"""Tests for scoped git commits (never git add -A)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.adapters.git_cli import GitCliAdapter
from ai_agent.adapters.approval import AutoApprovalGate
from ai_agent.domain.path_policy import PathPolicy
from ai_agent.harness.touch_tracker import TouchTracker
from ai_agent.tools.git_tools import GitCommitTool


def _git_init(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("noise\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def test_commit_refuses_without_paths(tmp_path: Path) -> None:
    _git_init(tmp_path)
    git = GitCliAdapter(cwd=tmp_path, policy=PathPolicy())
    with pytest.raises(ValueError, match="paths required"):
        git.commit("msg")


def test_commit_only_scoped_paths(tmp_path: Path) -> None:
    _git_init(tmp_path)
    (tmp_path / "README.md").write_text("hello\nworld\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("changed noise\n", encoding="utf-8")
    git = GitCliAdapter(cwd=tmp_path, policy=PathPolicy())
    git.create_branch("agent/test-scoped")
    sha = git.commit("docs only", paths=["README.md"])
    assert sha
    # other.txt should remain dirty
    status = git.status()
    assert "other.txt" in status
    assert "README.md" not in status.replace("??", "")


@pytest.mark.asyncio
async def test_git_commit_tool_uses_tracker(tmp_path: Path) -> None:
    _git_init(tmp_path)
    (tmp_path / "README.md").write_text("hello\nbullet\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "noise.py").write_text("x=1\n", encoding="utf-8")
    tracker = TouchTracker()
    tracker.record("README.md")
    git = GitCliAdapter(cwd=tmp_path, policy=PathPolicy())
    tool = GitCommitTool(git, AutoApprovalGate(approve=True), tracker=tracker)
    result = await tool.execute(
        {"branch": "agent/evolve-test", "message": "docs: bullet"}
    )
    assert result.success, result.error
    assert "README.md" in (result.output or "")
    # Unrelated dirty tree should remain uncommitted (dir or file).
    assert "src" in git.status() or "noise.py" in git.status()
