"""request_approval tool — pause for human confirmation."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import ApprovalGate
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class RequestApprovalTool(BaseTool):
    """Ask a human before irreversible side effects."""

    def __init__(self, gate: ApprovalGate) -> None:
        super().__init__(
            name="request_approval",
            description=(
                "Request human approval before an irreversible action "
                "(publish, send, buy, delete). Pass a clear reason."
            ),
            parameters=[
                ToolParameter(
                    name="reason",
                    type="string",
                    description="What you want to do and why",
                    required=True,
                ),
            ],
        )
        self._gate = gate

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        reason = str(arguments["reason"]).strip()
        if not reason:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="reason must be non-empty",
            )
        approved = await self._gate.request(reason)
        if approved:
            return ToolResult(
                tool_name=self.name,
                success=True,
                output="approved",
            )
        return ToolResult(
            tool_name=self.name,
            success=False,
            output="",
            error="denied by user",
        )
