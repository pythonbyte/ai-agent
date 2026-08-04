"""Tests for ops metrics helpers."""

from __future__ import annotations

from pathlib import Path

from ai_agent.harness.ops_metrics import (
    compare_harness_versions,
    emit_ops_event,
    load_ops_events,
    replay_trace,
)


def test_emit_and_load(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    emit_ops_event(name="evolve.start", run_id="r1", detail="x", log_path=log)
    emit_ops_event(name="evolve.done", run_id="r1", success=True, log_path=log)
    events = load_ops_events(log_path=log, name="evolve.done")
    assert len(events) == 1
    assert events[0].success is True


def test_compare_and_replay(tmp_path: Path) -> None:
    assert compare_harness_versions(0.5, 0.8)["improved"] is True
    path = tmp_path / "trace.json"
    path.write_text('{"kind": "respond", "message": "ok"}', encoding="utf-8")
    assert replay_trace(path)["kind"] == "respond"
