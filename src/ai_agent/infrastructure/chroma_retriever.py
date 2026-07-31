"""Chroma-backed retriever and ingest helpers."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from ai_agent.domain.ports import Embedder, IngestDocument, RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "ai_agent_docs"


class InMemoryRetriever:
    """
    Simple cosine-similarity retriever for tests and offline demos.

    Stores embeddings in process memory — no chromadb required.
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._sources: list[str] = []
        self._vectors: list[list[float]] = []

    async def ingest(self, documents: list[IngestDocument]) -> int:
        if not documents:
            return 0
        texts = [doc.text for doc in documents]
        vectors = await self._embedder.embed(texts)
        for doc, vector in zip(documents, vectors, strict=True):
            doc_id = hashlib.sha256(f"{doc.source}:{doc.text}".encode()).hexdigest()[:16]
            self._ids.append(doc_id)
            self._texts.append(doc.text)
            self._sources.append(doc.source)
            self._vectors.append(vector)
        return len(documents)

    async def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]:
        if not self._vectors:
            return []
        query_vecs = await self._embedder.embed([query])
        query_vec = query_vecs[0]
        scored: list[tuple[float, int]] = []
        for idx, vector in enumerate(self._vectors):
            scored.append((_cosine(query_vec, vector), idx))
        scored.sort(key=lambda item: item[0], reverse=True)
        chunks: list[RetrievedChunk] = []
        for score, idx in scored[: max(1, top_k)]:
            chunks.append(
                RetrievedChunk(
                    id=self._ids[idx],
                    text=self._texts[idx],
                    score=score,
                    source=self._sources[idx],
                )
            )
        return chunks


class ChromaRetriever:
    """
    Chroma persistent retriever implementing Retriever (+ ingest).

    Requires the optional ``rag`` extra (chromadb).
    """

    def __init__(
        self,
        path: str | Path,
        embedder: Embedder,
        *,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        try:
            import chromadb  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "chromadb is required for ChromaRetriever. "
                "Install with: pip install 'ai-agent[rag]'"
            ) from exc

        self._embedder = embedder
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._client: Any = chromadb.PersistentClient(path=str(self._path))
        self._collection = self._client.get_or_create_collection(name=collection_name)

    async def ingest(self, documents: list[IngestDocument]) -> int:
        if not documents:
            return 0
        texts = [doc.text for doc in documents]
        vectors = await self._embedder.embed(texts)
        ids = [
            hashlib.sha256(f"{doc.source}:{doc.text}".encode()).hexdigest()[:16]
            for doc in documents
        ]
        metadatas = [{"source": doc.source, **doc.metadata} for doc in documents]
        self._collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Ingested %s documents into Chroma at %s", len(documents), self._path)
        return len(documents)

    async def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]:
        vectors = await self._embedder.embed([query])
        result = self._collection.query(
            query_embeddings=vectors,
            n_results=max(1, top_k),
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        chunks: list[RetrievedChunk] = []
        for idx, doc_id in enumerate(ids):
            distance = float(distances[idx]) if idx < len(distances) else 0.0
            meta = metadatas[idx] if idx < len(metadatas) else {}
            source = ""
            if isinstance(meta, dict):
                source = str(meta.get("source", ""))
            chunks.append(
                RetrievedChunk(
                    id=str(doc_id),
                    text=str(documents[idx]) if idx < len(documents) else "",
                    score=1.0 / (1.0 + distance),
                    source=source,
                )
            )
        return chunks


def load_docs_folder(docs_dir: str | Path) -> list[IngestDocument]:
    """Load text/markdown files from a directory into ingest documents."""
    root = Path(docs_dir)
    if not root.is_dir():
        raise ValueError(f"Docs directory not found: {root}")

    documents: list[IngestDocument] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".rst"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        for chunk in _chunk_text(text):
            documents.append(
                IngestDocument(
                    source=str(path.relative_to(root)),
                    text=chunk,
                )
            )
    return documents


def _chunk_text(text: str, *, max_chars: int = 800, overlap: int = 100) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def format_chunks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieval hits for the LLM observation channel."""
    if not chunks:
        return "(no results)"
    parts: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        parts.append(f"[{idx}] source={chunk.source} score={chunk.score:.3f}\n{chunk.text}")
    return "\n\n".join(parts)
