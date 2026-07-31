"""Domain models for Self-Harness experimental improvements."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FailureRecord(BaseModel):
    """One recorded agent failure used for weakness mining."""

    id: str
    agent_id: str
    message: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    tool_traces: list[dict[str, Any]] = Field(default_factory=list)
    context_summary: str = ""


class HarnessPatch(BaseModel):
    """
    Allowed harness edit surfaces (v0 — no arbitrary Python).

    Human must accept before merge into config.
    """

    id: str
    summary: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    system_prompt_append: str | None = None
    max_tool_rounds: int | None = None
    failure_ids: list[str] = Field(default_factory=list)
    status: Literal["proposed", "accepted", "rejected"] = "proposed"
