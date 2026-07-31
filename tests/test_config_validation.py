"""Tests for configuration validation and YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_agent.adapters.config_loader import ConfigError, load_agent_config
from ai_agent.domain.models import AgentConfig, Personality


class TestPersonalityValidation:
    def test_valid_personality(self) -> None:
        personality = Personality(tone="friendly", style="concise")
        assert personality.tone == "friendly"

    def test_defaults(self) -> None:
        personality = Personality()
        assert personality.tone == "professional"
        assert personality.style == "concise"


class TestAgentConfigValidation:
    def test_valid_config(self, sample_config: AgentConfig) -> None:
        assert sample_config.model.startswith("openai/")
        assert sample_config.max_tool_rounds == 5
        assert "calculator" in sample_config.tools

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            AgentConfig()  # type: ignore[call-arg]

    def test_load_yaml_config(self, tmp_path: Path) -> None:
        path = tmp_path / "agent.yaml"
        path.write_text(
            """
model: openai/gpt-4o-mini
system_prompt: Test prompt
tools:
  - calculator
""",
            encoding="utf-8",
        )
        config = load_agent_config(path)
        assert config.model == "openai/gpt-4o-mini"
        assert config.tools == ["calculator"]

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            load_agent_config(tmp_path / "missing.yaml")

    def test_invalid_yaml_shape(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_agent_config(path)
