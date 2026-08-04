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
    # Last compaction summary (durable hint; full history remains in messages).
    context_summary: str | None = None

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
        """
        Flatten history for OpenAI-compatible chat APIs (e.g. OpenRouter).

        Domain role ``tool`` is mapped to ``user`` on the wire. OpenRouter
        requires ``tool_call_id`` (and a preceding assistant ``tool_calls``)
        for ``role: tool``; this agent uses a JSON ReAct loop, not native
        function calling, so bare tool roles produce HTTP 400.
        """
        out: list[dict[str, str]] = []
        for m in self.messages:
            if m.role == "tool":
                label = m.tool_name or "tool"
                out.append(
                    {
                        "role": "user",
                        "content": f"[Observation from {label}]\n{m.content}",
                    }
                )
            else:
                out.append({"role": m.role, "content": m.content})
        return out
