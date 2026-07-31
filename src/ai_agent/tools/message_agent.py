"""message_agent tool — ask another agent via AgentMessenger."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import AgentMessenger
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class MessageAgentTool(BaseTool):
    """Delegate a sub-question to another registered agent."""

    def __init__(self, messenger: AgentMessenger, *, sender_id: str = "coordinator") -> None:
        super().__init__(
            name="message_agent",
            description=(
                "Ask another agent a question and receive its reply. "
                "Use for specialist handoffs (e.g. researcher)."
            ),
            parameters=[
                ToolParameter(
                    name="agent_id",
                    type="string",
                    description="Target agent id (e.g. researcher)",
                    required=True,
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Question or instruction for the target agent",
                    required=True,
                ),
            ],
        )
        self._messenger = messenger
        self._sender_id = sender_id

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        agent_id = str(arguments["agent_id"]).strip()
        message = str(arguments["message"]).strip()
        if not agent_id or not message:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="agent_id and message are required",
            )
        try:
            reply = await self._messenger.ask(
                agent_id,
                message,
                sender=self._sender_id,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=str(exc),
            )
        if reply.startswith("Error:"):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error=reply,
            )
        return ToolResult(tool_name=self.name, success=True, output=reply)
