"""Path allow/deny policy — immutable kernel surface (no I/O)."""

from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import BaseModel, Field

# Default engineer write surface (mutable product code) — not the safety kernel.
DEFAULT_ALLOW_PREFIXES: tuple[str, ...] = (
    "src/",
    "tests/",
    "config/",
    "README.md",
    "DECISIONS.md",
    "AGENTS.md",
    "docs/",
)

DEFAULT_DENY_PREFIXES: tuple[str, ...] = (
    ".env",
    ".git/",
    ".ai_agent/",
    "src/ai_agent/domain/path_policy.py",
    "src/ai_agent/domain/platform.py",
)


class PathPolicy(BaseModel):
    """
    Least-privilege path gates for workspace writes.

    Part of immutable kernel K — evolver must not rewrite this module.
    """

    allow_prefixes: list[str] = Field(default_factory=lambda: list(DEFAULT_ALLOW_PREFIXES))
    deny_prefixes: list[str] = Field(default_factory=lambda: list(DEFAULT_DENY_PREFIXES))
    max_patch_bytes: int = Field(default=200_000, ge=1)
    max_file_bytes: int = Field(default=200_000, ge=1)

    def normalize(self, relative_path: str) -> str:
        cleaned = relative_path.strip().replace("\\", "/")
        while cleaned.startswith("./"):
            cleaned = cleaned[2:]
        if cleaned.startswith("/") or ".." in PurePosixPath(cleaned).parts:
            raise ValueError(f"Unsafe path: {relative_path}")
        return cleaned

    def is_denied(self, relative_path: str) -> bool:
        path = self.normalize(relative_path)
        for prefix in self.deny_prefixes:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                return True
        return False

    def is_allowed(self, relative_path: str) -> bool:
        path = self.normalize(relative_path)
        if self.is_denied(path):
            return False
        for prefix in self.allow_prefixes:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                return True
        return False

    def assert_writable(self, relative_path: str) -> str:
        path = self.normalize(relative_path)
        if not self.is_allowed(path):
            raise PermissionError(f"Path not writable under policy: {path}")
        return path
