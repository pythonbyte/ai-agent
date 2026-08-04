"""Domain models for evolve, gene bank, spawn budgets, and merge policy."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

HarnessWhere = Literal["prompt", "knowledge", "runtime", "config"]


class CheckResult(BaseModel):
    """Outcome of a local verification suite (pytest/ruff/mypy)."""

    success: bool
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


class SpawnBudget(BaseModel):
    """Limits for dynamic sub-agent graphs (kernel-enforced)."""

    max_depth: int = Field(default=2, ge=1, le=8)
    max_children: int = Field(default=4, ge=1, le=32)
    ask_timeout_seconds: float = Field(default=60.0, gt=0)


class EvolveRun(BaseModel):
    """Durable evolve-run checkpoint (pause / inspect / resume)."""

    id: str
    intent: str
    status: Literal[
        "planned",
        "editing",
        "verifying",
        "awaiting_approval",
        "publishing",
        "done",
        "failed",
        "stopped",
    ] = "planned"
    branch: str | None = None
    pr_url: str | None = None
    plan_path: str | None = None
    fix_rounds: int = 0
    max_fix_rounds: int = 3
    last_check_log: str = ""
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class EvolveOrganism(BaseModel):
    """Long-lived identity for wake/sleep cycles (Phase 2)."""

    id: str
    goals: list[str] = Field(default_factory=list)
    last_run_id: str | None = None
    last_sha: str | None = None
    next_wake_at: str | None = None
    merges_today: int = 0
    stopped: bool = False
    notes: str = ""


class MergePolicy(BaseModel):
    """Deterministic auto-merge gates (Phase 2 kernel)."""

    require_ci_green: bool = True
    max_diff_lines: int = Field(default=800, ge=1)
    max_merges_per_day: int = Field(default=5, ge=0)
    allowed_path_prefixes: list[str] = Field(
        default_factory=lambda: ["src/", "tests/", "config/"]
    )
    deny_path_prefixes: list[str] = Field(
        default_factory=lambda: [".env", "src/ai_agent/domain/path_policy.py"]
    )


class GeneCell(BaseModel):
    """HarnessBank cell: (where, why) → verified harness surface."""

    where: HarnessWhere
    why: str
    model_id: str
    summary: str
    system_prompt_append: str | None = None
    max_tool_rounds: int | None = None
    parent_id: str | None = None
    train_score: float | None = None
    activation_seen: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    id: str = ""


class ScreeningResult(BaseModel):
    """Gated Harness Screening outcome (deterministic evaluator)."""

    passed: bool
    validity_ok: bool = True
    activation_ok: bool = False
    significance_ok: bool = False
    gain_ok: bool = False
    reason: str = ""
    sample_score: float | None = None
    parent_score: float | None = None


class OpsEvent(BaseModel):
    """Structured ops metric event (log-level v1)."""

    name: str
    run_id: str | None = None
    success: bool | None = None
    latency_ms: int | None = None
    cost_units: float | None = None
    detail: str = ""
    at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
