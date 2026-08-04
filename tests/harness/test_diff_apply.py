"""Tests for unified diff apply (pure)."""

from __future__ import annotations

import pytest

from ai_agent.harness.diff_apply import apply_hunks_to_text, parse_unified_diff


def test_parse_and_apply_simple_change() -> None:
    original = "a\nb\nc\n"
    patch = """diff --git a/f.txt b/f.txt
--- a/f.txt
+++ b/f.txt
@@ -1,3 +1,3 @@
 a
-b
+B
 c
"""
    files = parse_unified_diff(patch)
    assert len(files) == 1
    assert files[0].path == "f.txt"
    updated = apply_hunks_to_text(original, files[0].hunks)
    assert updated == "a\nB\nc\n"


def test_parse_new_file() -> None:
    patch = """diff --git a/new.txt b/new.txt
--- /dev/null
+++ b/new.txt
@@ -0,0 +1,2 @@
+hello
+world
"""
    files = parse_unified_diff(patch)
    assert files[0].is_new
    updated = apply_hunks_to_text("", files[0].hunks)
    assert "hello" in updated
    assert "world" in updated


def test_empty_patch_raises() -> None:
    with pytest.raises(ValueError):
        parse_unified_diff("")


def test_context_mismatch_raises() -> None:
    hunks = (
        "@@ -1,1 +1,1 @@",
        "-nope",
        "+yes",
    )
    with pytest.raises(ValueError, match="mismatch"):
        apply_hunks_to_text("actual\n", hunks)
