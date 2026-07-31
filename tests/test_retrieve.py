"""Tests for retrieve tool and in-memory RAG helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.application.registry import ToolRegistry
from ai_agent.domain.models import AgentConfig, AgentDecision, Personality
from ai_agent.domain.ports import IngestDocument, RetrievedChunk
from ai_agent.infrastructure.chroma_retriever import (
    InMemoryRetriever,
    format_chunks,
    load_docs_folder,
)
from ai_agent.tools.retrieve import RetrieveTool
from tests.conftest import ScriptedLLM, decision_call_tools, make_agent


class FakeEmbedder:
    """Deterministic bag-of-words embedding for tests."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        vocab = ["agent", "tool", "rag", "memory", "hello", "ship"]
        for text in texts:
            lower = text.lower()
            vectors.append([float(lower.count(word)) for word in vocab])
        return vectors


def test_format_chunks_empty() -> None:
    assert format_chunks([]) == "(no results)"


def test_format_chunks() -> None:
    text = format_chunks([RetrievedChunk(id="1", text="hello", score=0.9, source="a.md")])
    assert "hello" in text
    assert "a.md" in text


def test_load_docs_folder(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("Agent tools and RAG memory.\n", encoding="utf-8")
    docs = load_docs_folder(tmp_path)
    assert len(docs) == 1
    assert docs[0].source == "a.md"


@pytest.mark.asyncio
async def test_inmemory_retrieve_and_tool() -> None:
    retriever = InMemoryRetriever(FakeEmbedder())
    await retriever.ingest(
        [
            IngestDocument(source="tools.md", text="The agent uses tools and RAG."),
            IngestDocument(source="other.md", text="Unrelated gardening tips."),
        ]
    )
    chunks = await retriever.retrieve("agent tools rag", top_k=1)
    assert chunks
    assert chunks[0].source == "tools.md"

    tool = RetrieveTool(retriever)
    result = await tool.execute({"query": "agent tools"})
    assert result.success is True
    assert "tools.md" in result.output


@pytest.mark.asyncio
async def test_agent_loop_uses_retrieve(sample_config: AgentConfig) -> None:
    retriever = InMemoryRetriever(FakeEmbedder())
    await retriever.ingest([IngestDocument(source="arch.md", text="Clean architecture agent kit.")])
    registry = ToolRegistry()
    registry.register(RetrieveTool(retriever))

    config = AgentConfig(
        model=sample_config.model,
        system_prompt=sample_config.system_prompt,
        max_tool_rounds=5,
        personality=Personality(),
        tools=["retrieve"],
        greeting="hi",
    )
    llm = ScriptedLLM(
        [
            decision_call_tools(("retrieve", {"query": "architecture"})),
            AgentDecision(kind="respond", message="Found architecture docs."),
        ]
    )
    agent = make_agent(config, llm, registry=registry)
    session = agent.create_session()
    result = await agent.step(session=session, user_input="What is this?")
    assert result.kind == "respond"
    assert result.tool_results
    assert result.tool_results[0]["success"] is True
