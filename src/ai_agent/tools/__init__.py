"""Built-in tools and a factory for the default registry."""

from __future__ import annotations

from pathlib import Path

from ai_agent.application.registry import ToolRegistry
from ai_agent.domain.ports import (
    AgentMessenger,
    HttpFetcher,
    MemoryStore,
    Retriever,
    WorkspaceReader,
)
from ai_agent.infrastructure.http_fetcher import HttpxFetcher
from ai_agent.infrastructure.workspace_fs import WorkspaceFS
from ai_agent.tools.calculator import CalculatorTool
from ai_agent.tools.datetime_tool import CurrentTimeTool
from ai_agent.tools.http_get import HttpGetTool
from ai_agent.tools.note import NoteTool
from ai_agent.tools.workspace_search import WorkspaceSearchTool

__all__ = [
    "CalculatorTool",
    "CurrentTimeTool",
    "HttpGetTool",
    "NoteTool",
    "WorkspaceSearchTool",
    "build_default_registry",
]


def build_default_registry(
    *,
    workspace_root: str | Path = ".",
    http_fetcher: HttpFetcher | None = None,
    workspace_reader: WorkspaceReader | None = None,
    memory_store: MemoryStore | None = None,
    retriever: Retriever | None = None,
    messenger: AgentMessenger | None = None,
    messenger_sender_id: str = "coordinator",
) -> ToolRegistry:
    """
    Register built-in tools into a fresh registry.

    Optional ports enable memory / retrieve / message_agent when provided.
    """
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    registry.register(NoteTool())

    fetcher = http_fetcher or HttpxFetcher()
    reader = workspace_reader or WorkspaceFS(workspace_root)
    registry.register(HttpGetTool(fetcher))
    registry.register(WorkspaceSearchTool(reader))

    if memory_store is not None:
        from ai_agent.tools.memory import MemoryTool

        registry.register(MemoryTool(memory_store))

    if retriever is not None:
        from ai_agent.tools.retrieve import RetrieveTool

        registry.register(RetrieveTool(retriever))

    if messenger is not None:
        from ai_agent.tools.message_agent import MessageAgentTool

        registry.register(
            MessageAgentTool(messenger, sender_id=messenger_sender_id),
        )

    return registry
