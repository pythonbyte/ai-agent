"""Subprocess test runner for pytest/ruff/mypy."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ai_agent.domain.platform import CheckResult

MAX_OUTPUT = 12_000


def _truncate(text: str, limit: int = MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n...[truncated]..."


class SubprocessTestRunner:
    """Run verification commands with timeout and output caps."""

    def __init__(self, *, cwd: str | Path = ".") -> None:
        self.cwd = Path(cwd)

    async def run(
        self,
        command: list[str],
        *,
        timeout_seconds: float = 120.0,
    ) -> CheckResult:
        joined = " ".join(command)
        if not command:
            return CheckResult(
                success=False,
                command="",
                exit_code=1,
                stderr="empty command",
            )
        started = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return CheckResult(
                success=False,
                command=joined,
                exit_code=127,
                stderr=str(exc),
            )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=max(0.1, timeout_seconds),
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return CheckResult(
                success=False,
                command=joined,
                exit_code=-1,
                stderr=f"timed out after {timeout_seconds}s",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        stdout = _truncate(stdout_b.decode("utf-8", errors="replace"))
        stderr = _truncate(stderr_b.decode("utf-8", errors="replace"))
        code = proc.returncode if proc.returncode is not None else -1
        return CheckResult(
            success=code == 0,
            command=joined,
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
