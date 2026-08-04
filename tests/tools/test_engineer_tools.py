"""Tests for engineer tools wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.adapters.approval import AutoApprovalGate
from ai_agent.adapters.workspace_writer import WorkspaceWriterFS
from ai_agent.domain.path_policy import PathPolicy
from ai_agent.tools import build_default_registry
from ai_agent.tools.apply_patch import ApplyPatchTool
from ai_agent.tools.workspace_list import WorkspaceListTool


@pytest.mark.asyncio
async def test_engineer_tools_in_registry(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    registry = build_default_registry(
        workspace_root=tmp_path,
        approval_gate=AutoApprovalGate(approve=True),
        include_engineer_tools=True,
    )
    for name in (
        "workspace_list",
        "apply_patch",
        "run_checks",
        "git_status",
        "git_diff",
        "git_commit",
        "open_pull_request",
    ):
        assert registry.has(name)

    assert registry.has("write_file")
    assert registry.has("replace_in_file")


@pytest.mark.asyncio
async def test_workspace_list_and_apply(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    writer = WorkspaceWriterFS(tmp_path, policy=PathPolicy())
    writer.write_text("src/x.py", "1\n")
    listed = await WorkspaceListTool(writer).execute({})
    assert listed.success
    assert "src/x.py" in listed.output

    patch = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1 +1 @@
-1
+2
"""
    result = await ApplyPatchTool(writer).execute({"patch": patch})
    assert result.success
    assert (tmp_path / "src" / "x.py").read_text(encoding="utf-8") == "2\n"
