"""run_python tool — execute short Python snippets for computation."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import CodeExecutor
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class RunPythonTool(BaseTool):
    """
    Run a short Python program and return stdout/stderr.

    Use for calculations, transforms, and quick algorithms — not system admin.
    """

    def __init__(self, executor: CodeExecutor) -> None:
        super().__init__(
            name="run_python",
            description=(
                "Execute a short Python 3 snippet in a sandboxed subprocess and "
                "return stdout/stderr. Allowed: math/json/re/datetime and pure "
                "logic. Blocked: os/sys/subprocess/network/file open/eval/exec. "
                "Print results to stdout. Prefer this over guessing numeric work."
            ),
            parameters=[
                ToolParameter(
                    name="code",
                    type="string",
                    description="Python source to run (print the final answer)",
                    required=True,
                ),
                ToolParameter(
                    name="timeout_seconds",
                    type="number",
                    description="Max runtime in seconds (default 5, max 30)",
                    required=False,
                ),
            ],
        )
        self._executor = executor

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        code = arguments.get("code")
        if not isinstance(code, str) or not code.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="Missing required string argument: code",
            )

        timeout_raw = arguments.get("timeout_seconds", 5)
        try:
            timeout = float(timeout_raw) if timeout_raw is not None else 5.0
        except (TypeError, ValueError):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="timeout_seconds must be a number",
            )

        result = await self._executor.run(code, timeout_seconds=timeout)
        if result.timed_out:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=result.stdout,
                error=result.error or "timed out",
            )
        if not result.success:
            parts = []
            if result.stdout:
                parts.append(f"stdout:\n{result.stdout}")
            if result.stderr:
                parts.append(f"stderr:\n{result.stderr}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="\n".join(parts),
                error=result.error or "execution failed",
            )

        output = result.stdout
        if result.stderr.strip():
            output = f"{output}\nstderr:\n{result.stderr}" if output else result.stderr
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=output.strip() or "(no stdout)",
        )
