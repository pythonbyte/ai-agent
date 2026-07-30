"""Tool protocol — the contract every agent tool must satisfy."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """JSON-schema-ish parameter description exposed to the LLM."""

    name: str
    type: str = "string"
    description: str
    required: bool = True


class ToolSpec(BaseModel):
    """Serializable tool metadata for prompts and config."""

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Outcome of a single tool execution."""

    tool_name: str
    success: bool
    output: str
    error: str | None = None


@runtime_checkable
class Tool(Protocol):
    """
    Pluggable tool contract.

    Implementations live at the edge (tools/ or user code). The agent loop
    only depends on this protocol — keeping domain free of I/O details.
    """

    @property
    def name(self) -> str:
        """Unique tool identifier used in LLM decisions."""
        ...

    @property
    def description(self) -> str:
        """Human/LLM-readable description of what the tool does."""
        ...

    @property
    def parameters(self) -> list[ToolParameter]:
        """Expected arguments for this tool."""
        ...

    def spec(self) -> ToolSpec:
        """Return serializable metadata for prompts."""
        ...

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Run the tool with validated-ish arguments from the LLM."""
        ...


class BaseTool:
    """
    Convenience base class for built-in and custom tools.

    Prefer subclassing this over implementing Tool from scratch.
    """

    name: str
    description: str
    parameters: list[ToolParameter]

    def __init__(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters or []

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError
