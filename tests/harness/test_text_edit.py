"""Tests for replace_once / replace_in_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.adapters.workspace_writer import WorkspaceWriterFS
from ai_agent.domain.path_policy import PathPolicy
from ai_agent.harness.text_edit import replace_once
from ai_agent.tools.replace_in_file import ReplaceInFileTool


def test_replace_once_happy() -> None:
    assert replace_once("a\nb\nc\n", "b\n", "B\n") == "a\nB\nc\n"


def test_replace_once_missing_or_ambiguous() -> None:
    with pytest.raises(ValueError, match="not found"):
        replace_once("abc", "z", "Z")
    with pytest.raises(ValueError, match="times"):
        replace_once("xx", "x", "y")


@pytest.mark.asyncio
async def test_replace_in_file_tool(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("## Self-Evolving Engineer\n\nHi\n", encoding="utf-8")
    writer = WorkspaceWriterFS(tmp_path, policy=PathPolicy())
    tool = ReplaceInFileTool(writer)
    result = await tool.execute(
        {
            "path": "README.md",
            "old_string": "## Self-Evolving Engineer\n\nHi\n",
            "new_string": (
                "## Self-Evolving Engineer\n\n"
                "- Evolve artifacts live under `.ai_agent/evolve/<run_id>/`.\n\n"
                "Hi\n"
            ),
        }
    )
    assert result.success
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Evolve artifacts" in text
