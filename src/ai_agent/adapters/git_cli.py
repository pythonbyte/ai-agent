"""Git CLI adapter (no force push, no main push)."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitCliAdapter:
    """Thin git wrapper for evolve publishes."""

    def __init__(self, *, cwd: str | Path = ".") -> None:
        self.cwd = Path(cwd)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.cwd),
            capture_output=True,
            text=True,
            check=check,
        )

    def status(self) -> str:
        result = self._run("status", "--short", check=False)
        return (result.stdout or "") + (result.stderr or "")

    def diff(self, *, staged: bool = False) -> str:
        args = ["diff", "--staged"] if staged else ["diff"]
        result = self._run(*args, check=False)
        return result.stdout or ""

    def current_branch(self) -> str:
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def create_branch(self, name: str) -> None:
        cleaned = name.strip().replace(" ", "-")
        if cleaned in {"main", "master"}:
            raise ValueError("refusing to create protected branch name")
        self._run("checkout", "-B", cleaned)

    def commit(self, message: str) -> str:
        msg = message.strip()
        if not msg:
            raise ValueError("commit message required")
        self._run("add", "-A")
        # Allow empty? No — fail clearly
        status = self._run("status", "--porcelain", check=False)
        if not (status.stdout or "").strip():
            raise ValueError("nothing to commit")
        self._run("commit", "-m", msg)
        sha = self._run("rev-parse", "HEAD")
        return sha.stdout.strip()

    def push_branch(self, name: str) -> None:
        branch = name.strip()
        if branch in {"main", "master"}:
            raise ValueError("refusing to push directly to main/master")
        current = self.current_branch()
        if current in {"main", "master"}:
            raise ValueError("refusing to push while on main/master")
        self._run("push", "-u", "origin", branch)
