"""OpenRouter embeddings adapter implementing Embedder."""

from __future__ import annotations

import os

import httpx

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_EMBED_MODEL = "openai/text-embedding-3-small"


class OpenRouterEmbedder:
    """Infrastructure adapter for OpenRouter embeddings HTTP API."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_EMBED_MODEL,
        api_key: str | None = None,
        base_url: str = OPENROUTER_EMBEDDINGS_URL,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        items = data.get("data")
        if not isinstance(items, list):
            raise ValueError(f"Unexpected embeddings response: {data}")

        ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
        vectors: list[list[float]] = []
        for item in ordered:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("Embedding vector missing from response")
            vectors.append([float(x) for x in embedding])
        return vectors
