"""Domain ports — I/O boundaries used by tools and orchestration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ai_agent.domain.models import CompactionConfig
from ai_agent.domain.platform import CheckResult
from ai_agent.domain.state import ConversationState


class RetrievedChunk(BaseModel):
    """One retrieval hit returned to the agent loop."""

    id: str
    text: str
    score: float = 0.0
    source: str = ""


class SearchHit(BaseModel):
    """One web-search result."""

    title: str
    url: str
    snippet: str = ""


@runtime_checkable
class HttpFetcher(Protocol):
    """Fetch a URL body with safety limits applied by the implementation."""

    async def get_text(self, url: str, *, max_bytes: int) -> str:
        """Return response body as text, truncated to max_bytes."""
        ...


@runtime_checkable
class WebSearcher(Protocol):
    """Search the public web for a query."""

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchHit]:
        """Return ranked search hits (title, url, snippet)."""
        ...


@runtime_checkable
class WorkspaceReader(Protocol):
    """Sandboxed read/search over a workspace root."""

    def resolve_safe(self, relative_path: str) -> str:
        """Return absolute path if inside root; raise ValueError otherwise."""
        ...

    def read_text(self, relative_path: str, *, max_bytes: int) -> str:
        """Read a file under the workspace root."""
        ...

    def search(
        self,
        query: str,
        *,
        glob_pattern: str,
        max_results: int,
    ) -> list[tuple[str, str]]:
        """
        Search files under root.

        Returns list of (relative_path, matching_snippet).
        """
        ...


@runtime_checkable
class SessionStore(Protocol):
    """Persist and reload conversation sessions."""

    def save(self, agent_id: str, state: ConversationState) -> None: ...

    def load(self, agent_id: str) -> ConversationState | None: ...


@runtime_checkable
class MemoryStore(Protocol):
    """Durable key/value memory for the memory tool."""

    def put(self, key: str, value: str) -> None: ...

    def get(self, key: str) -> str | None: ...

    def list_keys(self, prefix: str = "") -> list[str]: ...


@runtime_checkable
class Embedder(Protocol):
    """Embed text for retrieval indexing and queries."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class Retriever(Protocol):
    """Semantic retrieval over an indexed corpus."""

    async def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]: ...


@runtime_checkable
class AgentMessenger(Protocol):
    """Synchronous ask of another agent via the runtime."""

    async def ask(
        self,
        target_id: str,
        message: str,
        *,
        sender: str,
    ) -> str: ...


@runtime_checkable
class ApprovalGate(Protocol):
    """Human-in-the-loop approval for irreversible actions."""

    async def request(self, prompt: str) -> bool:
        """Return True if the user approves the action described by prompt."""
        ...


class PackedContext(BaseModel):
    """Wire-format messages produced by a ContextPacker (may be compacted)."""

    messages: list[dict[str, str]]
    compacted: bool = False
    summary: str | None = None
    original_chars: int = 0
    packed_chars: int = 0


@runtime_checkable
class ContextPacker(Protocol):
    """
    Build the message list sent to the LLM for one decide step.

    Must not destroy ConversationState history — packing is a read-side view.
    """

    async def pack(
        self,
        state: ConversationState,
        *,
        budget: CompactionConfig,
    ) -> PackedContext: ...


class CodeExecutionResult(BaseModel):
    """Outcome of a sandboxed code run."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    error: str | None = None


@runtime_checkable
class CodeExecutor(Protocol):
    """Execute a short code snippet and return captured I/O."""

    async def run(self, code: str, *, timeout_seconds: float = 5.0) -> CodeExecutionResult: ...


@runtime_checkable
class WorkspaceWriter(Protocol):
    """Sandboxed writes under a PathPolicy (apply patch / write text)."""

    def write_text(self, relative_path: str, content: str) -> str:
        """Write file; return relative path written."""
        ...

    def apply_unified_diff(self, patch_text: str) -> list[str]:
        """Apply a unified diff; return list of touched relative paths."""
        ...

    def list_paths(self, *, glob_pattern: str = "**/*", max_results: int = 200) -> list[str]:
        """List relative file paths under the workspace root."""
        ...


@runtime_checkable
class TestRunner(Protocol):
    """Run verification commands (pytest/ruff/mypy)."""

    async def run(self, command: list[str], *, timeout_seconds: float = 120.0) -> CheckResult: ...


@runtime_checkable
class GitPort(Protocol):
    """Minimal git operations for evolve publishes."""

    def status(self) -> str: ...

    def diff(self, *, staged: bool = False) -> str: ...

    def create_branch(self, name: str) -> None: ...

    def commit(self, message: str) -> str:
        """Stage allowlisted changes and commit; return commit sha."""
        ...

    def push_branch(self, name: str) -> None: ...

    def current_branch(self) -> str: ...


@runtime_checkable
class PullRequestPort(Protocol):
    """Open (and optionally merge) pull requests."""

    def create_pr(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> str:
        """Return PR URL."""
        ...

    def merge_pr(self, pr_url: str) -> None: ...

    def wait_checks(
        self,
        pr_url: str,
        *,
        timeout_seconds: float = 600.0,
    ) -> bool:
        """Return True if checks are green."""
        ...


@runtime_checkable
class SchedulerPort(Protocol):
    """Schedule organism wake-ups (file/cron backed)."""

    def schedule_wake(self, *, at_iso: str, payload: str) -> None: ...

    def clear(self) -> None: ...

    def is_stopped(self) -> bool: ...


@runtime_checkable
class AgentSpawner(Protocol):
    """Dynamic sub-agent spawn via the runtime."""

    async def spawn(
        self,
        role: str,
        message: str,
        *,
        sender: str,
        depth: int = 0,
    ) -> str:
        """Spawn (or reuse) a role agent, ask ``message``, return reply."""
        ...


class IngestDocument(BaseModel):
    """Document payload for ingest pipelines."""

    source: str
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)
