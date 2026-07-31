"""Domain ports — I/O boundaries used by tools and orchestration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

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


class IngestDocument(BaseModel):
    """Document payload for ingest pipelines."""

    source: str
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)
