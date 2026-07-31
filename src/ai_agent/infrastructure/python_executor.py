"""Subprocess-backed Python executor (timeout + output caps)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

from ai_agent.application.python_guard import validate_python_code
from ai_agent.domain.ports import CodeExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_CHARS = 8_000


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n...[truncated]..."


class SubprocessPythonExecutor:
    """
    Run Python in an isolated subprocess under a temp cwd.

    Not a full container sandbox — pair with ``validate_python_code`` and
    short timeouts. Prefer Docker/Firecracker for untrusted multi-tenant use.
    """

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        max_output_chars: int = MAX_OUTPUT_CHARS,
    ) -> None:
        self._python = python_executable or sys.executable
        self._max_output_chars = max_output_chars

    async def run(
        self,
        code: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> CodeExecutionResult:
        try:
            validate_python_code(code)
        except ValueError as exc:
            return CodeExecutionResult(success=False, error=str(exc))

        timeout = max(0.1, min(float(timeout_seconds), 30.0))
        with tempfile.TemporaryDirectory(prefix="ai_agent_py_") as tmp:
            script = Path(tmp) / "snippet.py"
            script.write_text(code.strip() + "\n", encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = ""
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = await asyncio.create_subprocess_exec(
                    self._python,
                    str(script),
                    cwd=tmp,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            except OSError as exc:
                return CodeExecutionResult(success=False, error=f"failed to start python: {exc}")

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                logger.warning("python_exec_timeout timeout=%s", timeout)
                return CodeExecutionResult(
                    success=False,
                    timed_out=True,
                    error=f"execution timed out after {timeout}s",
                )

            stdout = _truncate(stdout_b.decode("utf-8", errors="replace"), self._max_output_chars)
            stderr = _truncate(stderr_b.decode("utf-8", errors="replace"), self._max_output_chars)
            exit_code = proc.returncode if proc.returncode is not None else -1
            ok = exit_code == 0
            return CodeExecutionResult(
                success=ok,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                error=None if ok else (stderr.strip() or f"exit code {exit_code}"),
            )
