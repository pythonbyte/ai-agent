"""Domain layer — pure types and protocols (no I/O)."""

from ai_agent.domain.harness_improve import FailureRecord, HarnessPatch
from ai_agent.domain.models import (
    AgentConfig,
    AgentDecision,
    CompactionConfig,
    Message,
    Personality,
    StepResult,
    ToolCallRequest,
)
from ai_agent.domain.ports import (
    AgentMessenger,
    ApprovalGate,
    ContextPacker,
    Embedder,
    HttpFetcher,
    IngestDocument,
    MemoryStore,
    PackedContext,
    RetrievedChunk,
    Retriever,
    SessionStore,
    WorkspaceReader,
)
from ai_agent.domain.state import ConversationState
from ai_agent.domain.tool import BaseTool, Tool, ToolParameter, ToolResult, ToolSpec

__all__ = [
    "AgentConfig",
    "AgentDecision",
    "AgentMessenger",
    "ApprovalGate",
    "BaseTool",
    "CompactionConfig",
    "ContextPacker",
    "ConversationState",
    "Embedder",
    "FailureRecord",
    "HarnessPatch",
    "HttpFetcher",
    "IngestDocument",
    "MemoryStore",
    "Message",
    "PackedContext",
    "Personality",
    "RetrievedChunk",
    "Retriever",
    "SessionStore",
    "StepResult",
    "Tool",
    "ToolCallRequest",
    "ToolParameter",
    "ToolResult",
    "ToolSpec",
    "WorkspaceReader",
]
