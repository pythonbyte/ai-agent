"""Tests for MergePolicy evaluation."""

from __future__ import annotations

from ai_agent.domain.merge_policy import may_merge
from ai_agent.domain.platform import MergePolicy


def test_may_merge_happy_path() -> None:
    ok, reason = may_merge(
        MergePolicy(),
        ci_green=True,
        diff_lines=10,
        changed_paths=["src/foo.py"],
        merges_today=0,
        stopped=False,
    )
    assert ok
    assert reason == "ok"


def test_may_merge_stop_and_ci() -> None:
    policy = MergePolicy()
    ok, reason = may_merge(
        policy,
        ci_green=True,
        diff_lines=1,
        changed_paths=["src/a.py"],
        merges_today=0,
        stopped=True,
    )
    assert not ok
    assert "STOP" in reason

    ok, reason = may_merge(
        policy,
        ci_green=False,
        diff_lines=1,
        changed_paths=["src/a.py"],
        merges_today=0,
        stopped=False,
    )
    assert not ok
    assert "CI" in reason


def test_may_merge_budget_and_paths() -> None:
    policy = MergePolicy(max_merges_per_day=1, max_diff_lines=5)
    ok, _ = may_merge(
        policy,
        ci_green=True,
        diff_lines=6,
        changed_paths=["src/a.py"],
        merges_today=0,
        stopped=False,
    )
    assert not ok

    ok, reason = may_merge(
        policy,
        ci_green=True,
        diff_lines=1,
        changed_paths=["src/a.py"],
        merges_today=1,
        stopped=False,
    )
    assert not ok
    assert "budget" in reason

    ok, reason = may_merge(
        policy,
        ci_green=True,
        diff_lines=1,
        changed_paths=[".env"],
        merges_today=0,
        stopped=False,
    )
    assert not ok
    assert "path" in reason
