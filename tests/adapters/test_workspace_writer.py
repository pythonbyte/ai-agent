"""Tests for workspace writer + PathPolicy jail."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.adapters.workspace_writer import WorkspaceWriterFS
from ai_agent.domain.path_policy import PathPolicy


def test_write_and_list(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    writer = WorkspaceWriterFS(tmp_path, policy=PathPolicy())
    writer.write_text("src/hello.py", "x = 1\n")
    paths = writer.list_paths(glob_pattern="src/**/*.py")
    assert "src/hello.py" in paths


def test_apply_patch_under_policy(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "a.py"
    target.write_text("old\n", encoding="utf-8")
    writer = WorkspaceWriterFS(tmp_path, policy=PathPolicy())
    patch = """diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-old
+new
"""
    touched = writer.apply_unified_diff(patch)
    assert touched == ["src/a.py"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_denied_kernel_write(tmp_path: Path) -> None:
    writer = WorkspaceWriterFS(tmp_path, policy=PathPolicy())
    with pytest.raises(PermissionError):
        writer.write_text("src/ai_agent/domain/path_policy.py", "nope")
