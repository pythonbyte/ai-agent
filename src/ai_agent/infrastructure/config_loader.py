"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ai_agent.domain.models import AgentConfig


class ConfigError(ValueError):
    """Raised when configuration cannot be loaded or validated."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a plain dict."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(data).__name__}")
    return data


def load_agent_config(path: str | Path) -> AgentConfig:
    """Load and validate an AgentConfig from YAML."""
    raw = load_yaml(path)
    try:
        return AgentConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid agent config in {path}:\n{exc}") from exc
