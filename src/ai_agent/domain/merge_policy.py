"""MergePolicy evaluation (deterministic kernel)."""

from __future__ import annotations

from ai_agent.domain.path_policy import PathPolicy
from ai_agent.domain.platform import MergePolicy


def may_merge(
    policy: MergePolicy,
    *,
    ci_green: bool,
    diff_lines: int,
    changed_paths: list[str],
    merges_today: int,
    stopped: bool,
) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    if stopped:
        return False, "STOP kill switch active"
    if policy.require_ci_green and not ci_green:
        return False, "CI not green"
    if diff_lines > policy.max_diff_lines:
        return False, f"diff too large ({diff_lines} > {policy.max_diff_lines})"
    if merges_today >= policy.max_merges_per_day:
        return False, "daily merge budget exhausted"
    path_policy = PathPolicy(
        allow_prefixes=list(policy.allowed_path_prefixes),
        deny_prefixes=list(policy.deny_path_prefixes),
    )
    for path in changed_paths:
        if not path_policy.is_allowed(path):
            return False, f"path not allowed for merge: {path}"
    return True, "ok"
