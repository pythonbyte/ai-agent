"""Tests for LLM provider resolution (OpenAI vs OpenRouter)."""

from __future__ import annotations

import pytest

from ai_agent.adapters.llm import normalize_model_for_provider, resolve_llm_settings


def test_normalize_model_strips_openai_prefix() -> None:
    assert normalize_model_for_provider("openai/gpt-4o-mini", "openai") == "gpt-4o-mini"
    assert (
        normalize_model_for_provider("openai/gpt-4o-mini", "openrouter") == "openai/gpt-4o-mini"
    )


def test_resolve_openai_via_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = resolve_llm_settings("openai/gpt-4o-mini")
    assert settings.provider == "openai"
    assert settings.model == "gpt-4o-mini"
    assert "api.openai.com" in settings.base_url
    assert settings.api_key == "sk-test"


def test_resolve_openai_when_only_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-only")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = resolve_llm_settings("gpt-4o-mini")
    assert settings.provider == "openai"
    assert settings.api_key == "sk-only"


def test_resolve_openrouter_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    settings = resolve_llm_settings("openai/gpt-4o-mini")
    assert settings.provider == "openrouter"
    assert settings.api_key == "or-key"


def test_openai_provider_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        resolve_llm_settings("gpt-4o-mini")
