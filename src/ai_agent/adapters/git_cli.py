"""Git CLI adapter (no force push, no main push, no git add -A)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ai_agent.domain.path_policy import PathPolicy


class GitCliAdapter:
    """Thin git wrapper for evolve publishes."""

    def __init__(
        self,
        *,
        cwd: str | Path = ".",
        policy: PathPolicy | None = None,
    ) -> None:
        self.cwd = Path(cwd)
        self.policy = policy or PathPolicy()

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

    def diff(self, *, staged: bool = False, paths: list[str] | None = None) -> str:
        args = ["diff", "--staged"] if staged else ["diff"]
        if paths:
            args.append("--")
            args.extend(paths)
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

    def _normalize_commit_paths(self, paths: list[str]) -> list[str]:
        if not paths:
            raise ValueError(
                "commit paths required — refusing git add -A. "
                "Pass only files touched by this evolve edit."
            )
        normalized: list[str] = []
        for raw in paths:
            path = self.policy.assert_writable(str(raw).strip())
            if path not in normalized:
                normalized.append(path)
        return normalized

    def commit(self, message: str, paths: list[str] | None = None) -> str:
        msg = message.strip()
        if not msg:
            raise ValueError("commit message required")
        to_add = self._normalize_commit_paths(list(paths or []))
        self._run("add", "--", *to_add)
        status = self._run("status", "--porcelain", "--", *to_add, check=False)
        if not (status.stdout or "").strip():
            raise ValueError(
                "nothing to commit for scoped paths: " + ", ".join(to_add)
            )
        self._run("commit", "-m", msg, "--", *to_add)
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
