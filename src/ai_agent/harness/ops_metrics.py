"""Structured ops metrics (log-level v1) + lightweight trace replay helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ai_agent.domain.platform import OpsEvent

logger = logging.getLogger("ai_agent.ops")

DEFAULT_OPS_LOG = Path(".ai_agent/ops/events.jsonl")


def emit_ops_event(
    *,
    name: str,
    run_id: str | None = None,
    success: bool | None = None,
    latency_ms: int | None = None,
    cost_units: float | None = None,
    detail: str = "",
    log_path: Path = DEFAULT_OPS_LOG,
) -> OpsEvent:
    """Append one OpsEvent to JSONL and emit a structured log line."""
    event = OpsEvent(
        name=name,
        run_id=run_id,
        success=success,
        latency_ms=latency_ms,
        cost_units=cost_units,
        detail=detail,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")
    logger.info(
        "ops name=%s run_id=%s success=%s latency_ms=%s detail=%s",
        event.name,
        event.run_id,
        event.success,
        event.latency_ms,
        event.detail[:120],
    )
    return event


def load_ops_events(
    *,
    log_path: Path = DEFAULT_OPS_LOG,
    name: str | None = None,
    limit: int = 100,
) -> list[OpsEvent]:
    """Load recent ops events (newest last), optional name filter."""
    if not log_path.is_file():
        return []
    events: list[OpsEvent] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = OpsEvent.model_validate_json(line)
        if name is not None and event.name != name:
            continue
        events.append(event)
    return events[-max(1, limit) :]


def replay_trace(path: Path) -> dict[str, object]:
    """Load a saved evolve/result or tool-trace JSON for inspection."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("trace must be a JSON object")
    return raw


def compare_harness_versions(
    parent_score: float | None,
    child_score: float | None,
    *,
    min_gain: float = 0.0,
) -> dict[str, object]:
    """Attribute gain to a child vs parent (eval ops hook)."""
    if parent_score is None or child_score is None:
        return {"comparable": False, "gain": None, "improved": False}
    gain = child_score - parent_score
    return {
        "comparable": True,
        "gain": gain,
        "improved": gain > min_gain,
        "parent_score": parent_score,
        "child_score": child_score,
    }
