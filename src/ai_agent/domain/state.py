"""Conversation / session state — pure domain, no I/O."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ai_agent.domain.models import Message
from ai_agent.domain.tool import ToolResult

Role = Literal["system", "user", "assistant", "tool"]


class ConversationState(BaseModel):
    """
    Per-session state for one agent conversation.

    Kept separate from the Agent instance so the runtime can host many
    concurrent sessions without shared mutable state on the agent itself.
    """

    messages: list[Message] = Field(default_factory=list)
    tool_traces: list[ToolResult] = Field(default_factory=list)
    done: bool = False
    greeting_sent: bool = False

    def add_message(
        self,
        role: Role,
        content: str,
        tool_name: str | None = None,
    ) -> None:
        self.messages.append(Message(role=role, content=content, tool_name=tool_name))

    def mark_done(self) -> None:
        self.done = True

    def as_chat_dicts(self) -> list[dict[str, str]]:
        """Flatten history for LLM providers that expect role/content dicts."""
        return [{"role": m.role, "content": m.content} for m in self.messages]
