"""Domain models for configuration, LLM decisions, and step results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Personality(BaseModel):
    """Light behavioral hints injected into the system prompt."""

    tone: str = "professional"
    style: str = "concise"


class AgentConfig(BaseModel):
    """
    External agent configuration (YAML/JSON).

    Tools are referenced by name and resolved against a ToolRegistry at runtime.
    """

    model: str
    system_prompt: str
    max_tool_rounds: int = 5
    personality: Personality = Field(default_factory=Personality)
    tools: list[str] = Field(default_factory=list)
    greeting: str | None = "Hello! How can I help you today?"
    workspace_root: str = "."
    sqlite_path: str = ".ai_agent/state.db"
    chroma_path: str = ".ai_agent/chroma"


class Message(BaseModel):
    """Single conversation turn stored in session state."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_name: str | None = None


class ToolCallRequest(BaseModel):
    """A tool invocation requested by the LLM."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


_DECISION_KINDS = frozenset({"respond", "call_tools", "done"})


class AgentDecision(BaseModel):
    """
    Structured LLM decision for one loop iteration.

    kind:
      - respond: send a message to the user and stop the tool loop
      - call_tools: execute one or more tools, then decide again
      - done: end the conversation

    Models sometimes put a tool name in ``kind`` (e.g. ``message_agent``);
    ``normalize_misplaced_tool_kind`` rewrites that into ``call_tools``.
    """

    kind: Literal["respond", "call_tools", "done"]
    message: str = ""
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_misplaced_tool_kind(cls, data: Any) -> Any:
        """If kind is a tool name, coerce to call_tools (+ synthesize tool_calls)."""
        if not isinstance(data, dict):
            return data
        kind = data.get("kind")
        if not isinstance(kind, str) or kind in _DECISION_KINDS:
            return data

        existing = data.get("tool_calls")
        if isinstance(existing, list) and existing:
            return {**data, "kind": "call_tools"}

        reserved = {"kind", "tool_calls"}
        arguments = {key: value for key, value in data.items() if key not in reserved}
        tool_message = arguments.pop("message", "")
        if not isinstance(tool_message, str):
            tool_message = str(tool_message)

        # When other tool-ish keys exist (e.g. agent_id), treat message as a tool arg.
        if any(key != "message" for key in arguments):
            if tool_message:
                arguments["message"] = tool_message
            user_message = ""
        else:
            user_message = tool_message

        return {
            "kind": "call_tools",
            "message": user_message,
            "tool_calls": [{"name": kind, "arguments": arguments}],
        }


class StepResult(BaseModel):
    """Public result of a single Agent.step() call."""

    message: str
    kind: Literal["respond", "done", "error"]
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    rounds_used: int = 0
