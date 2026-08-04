"""run_checks — pytest/ruff/mypy via TestRunner."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import TestRunner
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult

PRESETS: dict[str, list[str]] = {
    "pytest": ["python", "-m", "pytest", "-q", "--tb=short"],
    "ruff": ["python", "-m", "ruff", "check", "src", "tests"],
    "mypy": ["python", "-m", "mypy", "src"],
    "all": [],  # expanded below
}


class RunChecksTool(BaseTool):
    def __init__(self, runner: TestRunner) -> None:
        super().__init__(
            name="run_checks",
            description=(
                "Run verification: preset=pytest|ruff|mypy|all. "
                "Returns combined stdout/stderr and success flag."
            ),
            parameters=[
                ToolParameter(
                    name="preset",
                    type="string",
                    description="pytest | ruff | mypy | all (default pytest)",
                    required=False,
                ),
                ToolParameter(
                    name="timeout_seconds",
                    type="number",
                    description="Timeout per command (default 120)",
                    required=False,
                ),
            ],
        )
        self._runner = runner

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        preset = str(arguments.get("preset") or "pytest").strip().lower()
        timeout_raw = arguments.get("timeout_seconds", 120)
        try:
            timeout = float(timeout_raw) if timeout_raw is not None else 120.0
        except (TypeError, ValueError):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="timeout_seconds must be a number",
            )
        if preset == "all":
            commands = [PRESETS["pytest"], PRESETS["ruff"], PRESETS["mypy"]]
        elif preset in PRESETS and preset != "all":
            commands = [PRESETS[preset]]
        else:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=f"unknown preset: {preset}",
            )
        parts: list[str] = []
        ok = True
        for cmd in commands:
            result = await self._runner.run(cmd, timeout_seconds=timeout)
            ok = ok and result.success
            parts.append(
                f"$ {result.command}\n"
                f"exit={result.exit_code} duration_ms={result.duration_ms}\n"
                f"{result.stdout}\n{result.stderr}"
            )
        return ToolResult(
            tool_name=self.name,
            success=ok,
            output="\n---\n".join(parts),
            error=None if ok else "one or more checks failed",
        )
