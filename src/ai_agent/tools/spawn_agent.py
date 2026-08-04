"""spawn_agent tool — dynamically create and ask a specialist."""

from __future__ import annotations

from typing import Any

from ai_agent.domain.ports import AgentSpawner
from ai_agent.domain.tool import BaseTool, ToolParameter, ToolResult


class SpawnAgentTool(BaseTool):
    """Spawn a role-based sub-agent, ask it a question, return the reply."""

    def __init__(self, spawner: AgentSpawner, *, sender_id: str, depth: int = 0) -> None:
        super().__init__(
            name="spawn_agent",
            description=(
                "Spawn a specialist agent from a role template (e.g. researcher, "
                "engineer), ask it a message, and get the reply. Use for parallel "
                "or nested work. Respects depth/child budgets."
            ),
            parameters=[
                ToolParameter(
                    name="role",
                    type="string",
                    description="Role name matching config/agents/{role}.yaml",
                    required=True,
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Task or question for the spawned agent",
                    required=True,
                ),
            ],
        )
        self._spawner = spawner
        self._sender_id = sender_id
        self._depth = depth

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        role = str(arguments["role"]).strip()
        message = str(arguments["message"]).strip()
        if not role or not message:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="",
                error="role and message are required",
            )
        try:
            reply = await self._spawner.spawn(
                role,
                message,
                sender=self._sender_id,
                depth=self._depth,
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
