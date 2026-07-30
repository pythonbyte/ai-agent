"""OpenRouter LLM adapter with structured JSON output and retries."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 60.0


class LLMError(RuntimeError):
    """Raised when the LLM provider fails after retries."""


class OpenRouterLLM:
    """
    Infrastructure adapter implementing the application LLMPort.

    Uses OpenRouter's OpenAI-compatible HTTP API so we control retries,
    timeouts, and JSON parsing without SDK lock-in.
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str = OPENROUTER_URL,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url

    async def complete(
        self,
        messages: list[dict[str, str]],
        output_model: type[T],
    ) -> T:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not set. Export it or pass api_key=...")

        # Force JSON-shaped replies that match our Pydantic decision model.
        prompt_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "Respond with ONLY valid JSON matching the required schema. No markdown fences."
                ),
            },
        ]

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                content = await self._chat(prompt_messages)
                return output_model.model_validate_json(content)
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "llm_attempt_failed attempt=%s/%s error=%s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        raise LLMError(f"LLM failed after {self.max_retries} attempts: {last_error}")

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/pythonbyte/ai-agent",
            "X-Title": "ai-agent",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Unexpected LLM response shape: {data}") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM returned empty content")

        return content.strip()
