"""Tests for run_python tool and Python guardrails."""

from __future__ import annotations

import pytest

from ai_agent.adapters.python_executor import SubprocessPythonExecutor
from ai_agent.domain.ports import CodeExecutionResult
from ai_agent.harness.python_guard import validate_python_code
from ai_agent.tools.run_python import RunPythonTool


class TestPythonGuard:
    def test_allows_pure_math(self) -> None:
        validate_python_code("print(sum(range(10)))")

    def test_rejects_os_import(self) -> None:
        with pytest.raises(ValueError, match="blocked module"):
            validate_python_code("import os\nprint(os.getcwd())")

    def test_rejects_eval(self) -> None:
        with pytest.raises(ValueError, match="blocked call"):
            validate_python_code("print(eval('1+1'))")

    def test_rejects_open(self) -> None:
        with pytest.raises(ValueError, match="blocked call"):
            validate_python_code("open('/etc/passwd')")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            validate_python_code("   ")


class FakeExecutor:
    def __init__(self, result: CodeExecutionResult) -> None:
        self.result = result
        self.calls: list[tuple[str, float]] = []

    async def run(self, code: str, *, timeout_seconds: float = 5.0) -> CodeExecutionResult:
        self.calls.append((code, timeout_seconds))
        return self.result


@pytest.mark.asyncio
async def test_run_python_success() -> None:
    tool = RunPythonTool(
        FakeExecutor(CodeExecutionResult(success=True, stdout="42\n", exit_code=0))
    )
    result = await tool.execute({"code": "print(42)"})
    assert result.success is True
    assert result.output == "42"


@pytest.mark.asyncio
async def test_run_python_missing_code() -> None:
    tool = RunPythonTool(FakeExecutor(CodeExecutionResult(success=True, stdout="")))
    result = await tool.execute({})
    assert result.success is False


@pytest.mark.asyncio
async def test_run_python_timeout_path() -> None:
    tool = RunPythonTool(
        FakeExecutor(
            CodeExecutionResult(success=False, timed_out=True, error="execution timed out")
        )
    )
    result = await tool.execute({"code": "while True: pass"})
    assert result.success is False
    assert "timed out" in (result.error or "")


@pytest.mark.asyncio
async def test_subprocess_executor_runs_snippet() -> None:
    executor = SubprocessPythonExecutor()
    result = await executor.run("print(2 + 2)")
    assert result.success is True
    assert result.stdout.strip() == "4"


@pytest.mark.asyncio
async def test_subprocess_executor_blocks_os() -> None:
    executor = SubprocessPythonExecutor()
    result = await executor.run("import os\nprint(1)")
    assert result.success is False
    assert result.error is not None
    assert "blocked" in result.error


@pytest.mark.asyncio
async def test_subprocess_executor_timeout() -> None:
    executor = SubprocessPythonExecutor()
    result = await executor.run("import time\ntime.sleep(10)", timeout_seconds=0.2)
    # time is not blocked; timeout should fire
    assert result.timed_out is True or result.success is False
