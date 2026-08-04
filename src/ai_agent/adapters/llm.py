"""OpenAI-compatible LLM adapter (OpenRouter or OpenAI) with structured JSON + retries."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_TOKENS = 4096


class LLMError(RuntimeError):
    """Raised when the LLM provider fails after retries."""


@dataclass(frozen=True)
class LLMSettings:
    """Resolved HTTP endpoint + credentials for an OpenAI-compatible chat API."""

    provider: str
    base_url: str
    api_key: str
    model: str


def normalize_model_for_provider(model: str, provider: str) -> str:
    """
    Map YAML model ids across providers.

    OpenRouter often uses ``openai/gpt-4o-mini``; OpenAI expects ``gpt-4o-mini``.
    """
    cleaned = model.strip()
    if provider == "openai" and cleaned.startswith("openai/"):
        return cleaned.removeprefix("openai/")
    return cleaned


def resolve_llm_settings(
    model: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    provider: str | None = None,
) -> LLMSettings:
    """
    Choose OpenAI vs OpenRouter from env / explicit overrides.

    Priority:
    1. Explicit ``provider`` / ``LLM_PROVIDER`` (``openai`` | ``openrouter``)
    2. Explicit ``base_url`` / ``LLM_BASE_URL`` (implies custom OpenAI-compatible)
    3. If only ``OPENAI_API_KEY`` is set → OpenAI
    4. Else OpenRouter (``OPENROUTER_API_KEY``)
    """
    env_provider = (provider or os.getenv("LLM_PROVIDER") or "").strip().lower()
    env_base = (base_url or os.getenv("LLM_BASE_URL") or "").strip()

    if env_provider in {"openai", "openrouter"}:
        chosen = env_provider
    elif env_base:
        chosen = "custom"
    elif api_key:
        # Explicit key passed by caller — keep OpenRouter URL unless base overridden
        chosen = "openrouter"
    elif os.getenv("OPENAI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        chosen = "openai"
    elif os.getenv("OPENAI_API_KEY") and env_provider == "openai":
        chosen = "openai"
    else:
        chosen = "openrouter"

    if chosen == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY") or ""
        url = env_base or OPENAI_URL
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Export it or set LLM_PROVIDER=openai with a key."
            )
        return LLMSettings(
            provider="openai",
            base_url=url,
            api_key=key,
            model=normalize_model_for_provider(model, "openai"),
        )

    if chosen == "custom":
        key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        if not key:
            raise ValueError("LLM_API_KEY or OPENAI_API_KEY required with LLM_BASE_URL")
        return LLMSettings(
            provider="custom",
            base_url=env_base,
            api_key=key,
            model=model.strip(),
        )

    key = api_key or os.getenv("OPENROUTER_API_KEY") or ""
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. Export it, or set LLM_PROVIDER=openai "
            "with OPENAI_API_KEY to use OpenAI directly."
        )
    return LLMSettings(
        provider="openrouter",
        base_url=env_base or OPENROUTER_URL,
        api_key=key,
        model=model.strip(),
    )


class OpenRouterLLM:
    """
    Infrastructure adapter implementing the application LLMPort.

    OpenAI-compatible HTTP (OpenRouter by default, or OpenAI via LLM_PROVIDER=openai).
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str | None = None,
        provider: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        settings = resolve_llm_settings(
            model,
            api_key=api_key,
            base_url=base_url,
            provider=provider,
        )
        self.model = settings.model
        self.api_key = settings.api_key
        self.base_url = settings.base_url
        self.provider = settings.provider
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        logger.info(
            "llm_configured provider=%s model=%s base_url=%s",
            self.provider,
            self.model,
            self.base_url,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        output_model: type[T],
    ) -> T:
        if not self.api_key:
            raise ValueError("LLM API key is not set")

        prompt_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "Respond with ONLY valid JSON matching the required schema. "
                    "kind must be exactly respond, call_tools, or done — never a tool name. "
                    "No markdown fences."
                ),
            },
        ]

        last_error: Exception | None = None
        last_content = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                last_content = await self._chat(prompt_messages)
                return output_model.model_validate_json(last_content)
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "llm_attempt_failed attempt=%s/%s error=%s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    if last_content:
                        prompt_messages = [
                            *prompt_messages,
                            {"role": "assistant", "content": last_content},
                            {
                                "role": "user",
                                "content": (
                                    f"Your previous JSON was invalid: {exc}. "
                                    "Reply again with ONLY corrected JSON. "
                                    "kind must be respond, call_tools, or done."
                                ),
                            },
                        ]
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        raise LLMError(f"LLM failed after {self.max_retries} attempts: {last_error}")

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/pythonbyte/ai-agent"
            headers["X-Title"] = "ai-agent"

        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        # Newer OpenAI models (gpt-5 / o-series / luna) require max_completion_tokens.
        # OpenRouter still accepts classic max_tokens for most routed models.
        if self.provider in {"openai", "custom"}:
            payload["max_completion_tokens"] = self.max_tokens
        else:
            payload["max_tokens"] = self.max_tokens

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            if response.is_error:
                raise httpx.HTTPStatusError(
                    f"{response.status_code} {response.reason_phrase}: {response.text}",
                    request=response.request,
                    response=response,
                )
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Unexpected LLM response shape: {data}") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM returned empty content")

        return content.strip()
