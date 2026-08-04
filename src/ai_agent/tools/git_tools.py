"""Git tools for evolve publish path."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import ApprovalGate, GitPort
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult
from ai_agent.harness.touch_tracker import TouchTracker


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
    def __init__(self, git: GitPort, tracker: TouchTracker | None = None) -> None:
        super().__init__(
            name="git_diff",
            description=(
                "Show git diff. Defaults to files touched in this session when available."
            ),
            parameters=[
                ToolParameter(
                    name="staged",
                    type="boolean",
                    description="If true, show staged diff",
                    required=False,
                ),
                ToolParameter(
                    name="paths",
                    type="array",
                    description="Optional paths to limit the diff",
                    required=False,
                ),
            ],
        )
        self._git = git
        self._tracker = tracker

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        staged = bool(arguments.get("staged", False))
        paths: list[str] | None = _coerce_paths(arguments.get("paths")) or None
        if paths is None and self._tracker is not None:
            tracked = self._tracker.paths()
            paths = tracked or None
        try:
            output = self._git.diff(staged=staged, paths=paths)  # type: ignore[call-arg]
        except TypeError:
            output = self._git.diff(staged=staged)
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=output or "(empty diff)",
        )


class GitCommitTool(BaseTool):
    def __init__(
        self,
        git: GitPort,
        gate: ApprovalGate,
        tracker: TouchTracker | None = None,
    ) -> None:
        super().__init__(
            name="git_commit",
            description=(
                "Create/switch to a feature branch and commit ONLY files touched "
                "by this session (or explicit paths). Never git add -A. "
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
                ToolParameter(
                    name="paths",
                    type="array",
                    description=(
                        "Optional explicit relative paths to commit. "
                        "Defaults to files touched via replace_in_file/write_file/apply_patch."
                    ),
                    required=False,
                ),
            ],
            parallel_safe=False,
        )
        self._git = git
        self._gate = gate
        self._tracker = tracker

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

        paths = _coerce_paths(arguments.get("paths"))
        if not paths and self._tracker is not None:
            paths = self._tracker.paths()
        if not paths:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=(
                    "no scoped paths to commit. Edit with replace_in_file/write_file/"
                    "apply_patch first, or pass paths explicitly."
                ),
            )

        # Show only scoped status in the approval prompt.
        try:
            scoped_diff = self._git.diff(paths=paths)  # type: ignore[call-arg]
        except TypeError:
            scoped_diff = self._git.diff()
        if not (scoped_diff or "").strip():
            # Still allow if untracked new files exist in paths — status check later
            pass

        approved = await self._gate.request(
            "Create branch {branch!r} and commit ONLY these paths:\n"
            "{paths}\n\n"
            "Message: {message}\n\n"
            "Scoped diff:\n{diff}".format(
                branch=branch,
                paths="\n".join(f"- {p}" for p in paths),
                message=message,
                diff=(scoped_diff or "(no unstaged diff — may be new/untracked files)"),
            )
        )
        if not approved:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="denied by user",
            )
        try:
            self._git.create_branch(branch)
            sha = self._git.commit(message, paths=paths)
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
            output=f"branch={branch} sha={sha} paths={','.join(paths)}",
        )


def _coerce_paths(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        cleaned = raw.strip()
        return [cleaned] if cleaned else []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    return []
