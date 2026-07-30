"""Domain models for configuration, LLM decisions, and step results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class Message(BaseModel):
    """Single conversation turn stored in session state."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_name: str | None = None


class ToolCallRequest(BaseModel):
    """A tool invocation requested by the LLM."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentDecision(BaseModel):
    """
    Structured LLM decision for one loop iteration.

    kind:
      - respond: send a message to the user and stop the tool loop
      - call_tools: execute one or more tools, then decide again
      - done: end the conversation
    """

    kind: Literal["respond", "call_tools", "done"]
    message: str = ""
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)


class StepResult(BaseModel):
    """Public result of a single Agent.step() call."""

    message: str
    kind: Literal["respond", "done", "error"]
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    rounds_used: int = 0
