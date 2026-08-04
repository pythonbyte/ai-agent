"""Built-in tools and a factory for the default registry."""

from __future__ import annotations

from pathlib import Path

from ai_agent.adapters.gh_pr import GhPullRequestAdapter
from ai_agent.adapters.git_cli import GitCliAdapter
from ai_agent.adapters.http_fetcher import HttpxFetcher
from ai_agent.adapters.python_executor import SubprocessPythonExecutor
from ai_agent.adapters.test_runner import SubprocessTestRunner
from ai_agent.adapters.web_search import DuckDuckGoSearcher
from ai_agent.adapters.workspace_fs import WorkspaceFS
from ai_agent.adapters.workspace_writer import WorkspaceWriterFS
from ai_agent.domain.path_policy import PathPolicy
from ai_agent.domain.ports import (
    AgentMessenger,
    AgentSpawner,
    ApprovalGate,
    CodeExecutor,
    GitPort,
    HttpFetcher,
    MemoryStore,
    PullRequestPort,
    Retriever,
    TestRunner,
    WebSearcher,
    WorkspaceReader,
    WorkspaceWriter,
)
from ai_agent.harness.registry import ToolRegistry
from ai_agent.tools.calculator import CalculatorTool
from ai_agent.tools.datetime_tool import CurrentTimeTool
from ai_agent.tools.http_get import HttpGetTool
from ai_agent.tools.note import NoteTool
from ai_agent.tools.run_python import RunPythonTool
from ai_agent.tools.web_search import WebSearchTool
from ai_agent.tools.workspace_search import WorkspaceSearchTool

__all__ = [
    "CalculatorTool",
    "CurrentTimeTool",
    "HttpGetTool",
    "NoteTool",
    "RunPythonTool",
    "WebSearchTool",
    "WorkspaceSearchTool",
    "build_default_registry",
]


def build_default_registry(
    *,
    workspace_root: str | Path = ".",
    http_fetcher: HttpFetcher | None = None,
    workspace_reader: WorkspaceReader | None = None,
    workspace_writer: WorkspaceWriter | None = None,
    web_searcher: WebSearcher | None = None,
    memory_store: MemoryStore | None = None,
    retriever: Retriever | None = None,
    messenger: AgentMessenger | None = None,
    messenger_sender_id: str = "coordinator",
    approval_gate: ApprovalGate | None = None,
    code_executor: CodeExecutor | None = None,
    test_runner: TestRunner | None = None,
    git_port: GitPort | None = None,
    pr_port: PullRequestPort | None = None,
    path_policy: PathPolicy | None = None,
    spawner: AgentSpawner | None = None,
    spawn_depth: int = 0,
    include_engineer_tools: bool = False,
) -> ToolRegistry:
    """
    Register built-in tools into a fresh registry.

    Optional ports enable memory / retrieve / message_agent / request_approval /
    engineer tools / spawn_agent.
    """
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    registry.register(NoteTool())
    registry.register(RunPythonTool(code_executor or SubprocessPythonExecutor()))

    root = Path(workspace_root)
    fetcher = http_fetcher or HttpxFetcher()
    reader = workspace_reader or WorkspaceFS(root)
    searcher = web_searcher or DuckDuckGoSearcher()
    registry.register(HttpGetTool(fetcher))
    registry.register(WorkspaceSearchTool(reader))
    registry.register(WebSearchTool(searcher))

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

    if approval_gate is not None:
        from ai_agent.tools.request_approval import RequestApprovalTool

        registry.register(RequestApprovalTool(approval_gate))

    if spawner is not None:
        from ai_agent.tools.spawn_agent import SpawnAgentTool

        registry.register(
            SpawnAgentTool(spawner, sender_id=messenger_sender_id, depth=spawn_depth)
        )

    if include_engineer_tools:
        from ai_agent.tools.apply_patch import ApplyPatchTool
        from ai_agent.tools.git_tools import GitCommitTool, GitDiffTool, GitStatusTool
        from ai_agent.tools.open_pr import OpenPullRequestTool
        from ai_agent.tools.run_checks import RunChecksTool
        from ai_agent.tools.workspace_list import WorkspaceListTool

        writer = workspace_writer or WorkspaceWriterFS(root, policy=path_policy or PathPolicy())
        runner = test_runner or SubprocessTestRunner(cwd=root)
        git = git_port or GitCliAdapter(cwd=root)
        prs = pr_port or GhPullRequestAdapter(cwd=root)

        registry.register(WorkspaceListTool(writer))
        registry.register(ApplyPatchTool(writer))
        registry.register(RunChecksTool(runner))
        registry.register(GitStatusTool(git))
        registry.register(GitDiffTool(git))
        if approval_gate is not None:
            registry.register(GitCommitTool(git, approval_gate))
            registry.register(OpenPullRequestTool(prs, git, approval_gate))

    return registry
