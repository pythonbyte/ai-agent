"""GitHub PR adapter via the ``gh`` CLI."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path


class GhPullRequestAdapter:
    """Create/merge PRs and wait for checks using gh."""

    def __init__(self, *, cwd: str | Path = ".") -> None:
        self.cwd = Path(cwd)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gh", *args],
            cwd=str(self.cwd),
            capture_output=True,
            text=True,
            check=check,
        )

    def create_pr(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> str:
        if head in {"main", "master"}:
            raise ValueError("refusing to open PR from protected branch as head alone")
        result = self._run(
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--head",
            head,
            "--base",
            base,
        )
        url = (result.stdout or "").strip().splitlines()[-1]
        if not url.startswith("http"):
            raise RuntimeError(f"unexpected gh pr create output: {result.stdout}")
        return url

    def merge_pr(self, pr_url: str) -> None:
        self._run("pr", "merge", pr_url, "--merge", "--delete-branch")

    def wait_checks(
        self,
        pr_url: str,
        *,
        timeout_seconds: float = 600.0,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self._run(
                "pr",
                "checks",
                pr_url,
                check=False,
            )
            out = (result.stdout or "") + (result.stderr or "")
            lower = out.lower()
            if result.returncode == 0 and "fail" not in lower and "pending" not in lower:
                return True
            if "fail" in lower:
                return False
            time.sleep(5)
        return False
