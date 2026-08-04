"""open_pull_request tool — gh PR create with approval."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import ApprovalGate, GitPort, PullRequestPort
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class OpenPullRequestTool(BaseTool):
    def __init__(
        self,
        prs: PullRequestPort,
        git: GitPort,
        gate: ApprovalGate,
    ) -> None:
        super().__init__(
            name="open_pull_request",
            description=(
                "Push current branch and open a GitHub PR with title/body. "
                "Requires human approval. Call only AFTER a successful git_commit "
                "in a later round — never in the same tool batch, never from main."
            ),
            parameters=[
                ToolParameter(name="title", type="string", description="PR title", required=True),
                ToolParameter(
                    name="body",
                    type="string",
                    description="PR body / instructions of what changed",
                    required=True,
                ),
                ToolParameter(
                    name="base",
                    type="string",
                    description="Base branch (default main)",
                    required=False,
                ),
            ],
            parallel_safe=False,
        )
        self._prs = prs
        self._git = git
        self._gate = gate

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        title = str(arguments.get("title") or "").strip()
        body = str(arguments.get("body") or "").strip()
        base = str(arguments.get("base") or "main").strip() or "main"
        if not title or not body:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="title and body required",
            )
        head = self._git.current_branch()
        if head in {"main", "master"}:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="refusing to open PR from main/master — git_commit a feature branch first",
            )
        approved = await self._gate.request(
            f"Push branch {head!r} and open PR against {base!r}: {title}"
        )
        if not approved:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="denied by user",
            )
        try:
            self._git.push_branch(head)
            url = self._prs.create_pr(title=title, body=body, head=head, base=base)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        return ToolResult(tool_name=self.name, success=True, output=url)
