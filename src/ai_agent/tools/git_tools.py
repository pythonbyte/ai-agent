"""Git tools for evolve publish path."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import ApprovalGate, GitPort
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class GitStatusTool(BaseTool):
    def __init__(self, git: GitPort) -> None:
        super().__init__(
            name="git_status",
            description="Show short git status.",
            parameters=[],
        )
        self._git = git

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True, output=self._git.status() or "(clean)")


class GitDiffTool(BaseTool):
    def __init__(self, git: GitPort) -> None:
        super().__init__(
            name="git_diff",
            description="Show git diff (optional staged=true).",
            parameters=[
                ToolParameter(
                    name="staged",
                    type="boolean",
                    description="If true, show staged diff",
                    required=False,
                ),
            ],
        )
        self._git = git

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        staged = bool(arguments.get("staged", False))
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=self._git.diff(staged=staged) or "(empty diff)",
        )


class GitCommitTool(BaseTool):
    def __init__(self, git: GitPort, gate: ApprovalGate) -> None:
        super().__init__(
            name="git_commit",
            description=(
                "Create/switch to branch and commit all changes. "
                "Requires human approval. Never commits on main/master. "
                "Call alone in a round — never with open_pull_request."
            ),
            parameters=[
                ToolParameter(
                    name="branch",
                    type="string",
                    description="Branch name (e.g. agent/evolve-xyz)",
                    required=True,
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Commit message",
                    required=True,
                ),
            ],
            parallel_safe=False,
        )
        self._git = git
        self._gate = gate

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        branch = str(arguments.get("branch") or "").strip()
        message = str(arguments.get("message") or "").strip()
        if not branch or not message:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="branch and message required",
            )
        if branch in {"main", "master"}:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="refusing to commit on protected branch name",
            )
        approved = await self._gate.request(f"Create branch {branch!r} and commit: {message}")
        if not approved:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="denied by user",
            )
        try:
            self._git.create_branch(branch)
            sha = self._git.commit(message)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=f"branch={branch} sha={sha}",
        )
