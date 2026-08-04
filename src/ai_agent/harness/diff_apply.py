"""Pure unified-diff helpers (mutmut-friendly)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FilePatch:
    """One file's hunks from a unified diff."""

    path: str
    is_new: bool
    is_deleted: bool
    hunks: tuple[str, ...]


_FILE_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_PLUS_PLUS = re.compile(r"^\+\+\+ (?:[ab]/)?(.+)$")
_MINUS_MINUS = re.compile(r"^--- (?:[ab]/)?(.+)$")
_DEV_NULL = "/dev/null"


def parse_unified_diff(patch_text: str) -> list[FilePatch]:
    """
    Parse a simplified unified diff into per-file patches.

    Expects ``diff --git`` headers and standard @@ hunks.
    """
    text = patch_text.strip()
    if not text:
        raise ValueError("empty patch")

    files: list[FilePatch] = []
    current_path: str | None = None
    is_new = False
    is_deleted = False
    hunk_lines: list[str] = []
    in_hunk = False

    def flush() -> None:
        nonlocal current_path, is_new, is_deleted, hunk_lines, in_hunk
        if current_path is None:
            return
        files.append(
            FilePatch(
                path=current_path,
                is_new=is_new,
                is_deleted=is_deleted,
                hunks=tuple(hunk_lines),
            )
        )
        current_path = None
        is_new = False
        is_deleted = False
        hunk_lines = []
        in_hunk = False

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        header = _FILE_HEADER.match(line)
        if header:
            flush()
            current_path = header.group(2)
            continue
        mm = _MINUS_MINUS.match(line)
        if mm:
            if mm.group(1) == _DEV_NULL:
                is_new = True
            continue
        pp = _PLUS_PLUS.match(line)
        if pp:
            if pp.group(1) == _DEV_NULL:
                is_deleted = True
            else:
                current_path = pp.group(1)
            continue
        if line.startswith("@@"):
            in_hunk = True
            hunk_lines.append(line)
            continue
        if in_hunk:
            if line.startswith(("+", "-", " ")) or line == "\\ No newline at end of file":
                hunk_lines.append(line)
            else:
                in_hunk = False
    flush()
    if not files:
        raise ValueError("no file patches found in diff")
    return files


def apply_hunks_to_text(original: str, hunk_lines: tuple[str, ...]) -> str:
    """
    Apply unified hunk lines to original file text.

    Supports multiple @@ hunks concatenated in ``hunk_lines``.
    """
    if not hunk_lines:
        return original

    lines = original.splitlines()
    out: list[str] = []
    src_i = 0
    i = 0
    while i < len(hunk_lines):
        header = hunk_lines[i]
        if not header.startswith("@@"):
            i += 1
            continue
        match = re.match(
            r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
            header,
        )
        if not match:
            raise ValueError(f"bad hunk header: {header}")
        old_start = int(match.group(1))
        # unified diffs are 1-based; 0 means empty file
        old_idx = max(old_start - 1, 0)
        while src_i < old_idx and src_i < len(lines):
            out.append(lines[src_i])
            src_i += 1
        i += 1
        while i < len(hunk_lines) and not hunk_lines[i].startswith("@@"):
            row = hunk_lines[i]
            if row.startswith("\\"):
                i += 1
                continue
            if row.startswith(" "):
                if src_i >= len(lines) or lines[src_i] != row[1:]:
                    if src_i < len(lines) and lines[src_i].rstrip("\r") == row[1:].rstrip("\r"):
                        out.append(lines[src_i])
                        src_i += 1
                    else:
                        raise ValueError(
                            f"context mismatch at line {src_i + 1}: expected {row[1:]!r}"
                        )
                else:
                    out.append(lines[src_i])
                    src_i += 1
            elif row.startswith("-"):
                if src_i >= len(lines) or lines[src_i] != row[1:]:
                    if not (
                        src_i < len(lines)
                        and lines[src_i].rstrip("\r") == row[1:].rstrip("\r")
                    ):
                        raise ValueError(
                            f"delete mismatch at line {src_i + 1}: expected {row[1:]!r}"
                        )
                src_i += 1
            elif row.startswith("+"):
                out.append(row[1:])
            else:
                raise ValueError(f"invalid hunk line: {row!r}")
            i += 1
    while src_i < len(lines):
        out.append(lines[src_i])
        src_i += 1
    result = "\n".join(out)
    if original.endswith("\n"):
        result += "\n"
    return result
