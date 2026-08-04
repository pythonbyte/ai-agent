"""Phase 2 organism worker — wake, optional auto-merge under MergePolicy, reschedule."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ai_agent.adapters.scheduler import FileScheduler
from ai_agent.domain.merge_policy import may_merge
from ai_agent.domain.platform import EvolveOrganism, MergePolicy
from ai_agent.domain.ports import GitPort, PullRequestPort, SchedulerPort
from ai_agent.features.evolve.service import (
    DEFAULT_EVOLVE_ROOT,
    load_organism,
    load_run,
    save_organism,
)
from ai_agent.harness.ops_metrics import emit_ops_event

logger = logging.getLogger(__name__)


def ensure_organism(*, root: Path = DEFAULT_EVOLVE_ROOT, goals: list[str] | None = None) -> EvolveOrganism:
    existing = load_organism(root=root)
    if existing is not None:
        return existing
    organism = EvolveOrganism(id="organism_default", goals=list(goals or []))
    save_organism(organism, root=root)
    return organism


def try_auto_merge(
    *,
    pr_url: str,
    pr_port: PullRequestPort,
    git: GitPort,
    policy: MergePolicy,
    organism: EvolveOrganism,
    changed_paths: list[str],
    diff_lines: int,
    scheduler: SchedulerPort | None = None,
) -> tuple[bool, str]:
    """Wait CI and merge only if MergePolicy allows (Phase 2)."""
    if organism.stopped:
        return False, "organism stopped"
    sched = scheduler or FileScheduler(root=DEFAULT_EVOLVE_ROOT)
    if sched.is_stopped():
        return False, "STOP kill switch active"

    ci_green = pr_port.wait_checks(pr_url)
    allowed, reason = may_merge(
        policy,
        ci_green=ci_green,
        diff_lines=diff_lines,
        changed_paths=changed_paths,
        merges_today=organism.merges_today,
        stopped=organism.stopped or sched.is_stopped(),
    )
    if not allowed:
        emit_ops_event(name="evolve.merge_denied", success=False, detail=reason)
        return False, reason
    pr_port.merge_pr(pr_url)
    organism.merges_today += 1
    try:
        organism.last_sha = git.current_branch()
    except Exception:  # noqa: BLE001
        pass
    emit_ops_event(name="evolve.merged", success=True, detail=pr_url)
    return True, "merged"


def schedule_next_wake(
    organism: EvolveOrganism,
    *,
    root: Path = DEFAULT_EVOLVE_ROOT,
    hours: float = 24.0,
    payload: str = "resume",
) -> EvolveOrganism:
    """Persist organism sleep + file wake schedule; process may exit."""
    scheduler = FileScheduler(root=root)
    if scheduler.is_stopped() or organism.stopped:
        organism.stopped = True
        save_organism(organism, root=root)
        raise RuntimeError("STOP active; not scheduling wake")
    wake_at = datetime.now(UTC) + timedelta(hours=hours)
    organism.next_wake_at = wake_at.isoformat()
    scheduler.schedule_wake(at_iso=organism.next_wake_at, payload=payload)
    save_organism(organism, root=root)
    emit_ops_event(name="evolve.scheduled", detail=organism.next_wake_at)
    return organism


def worker_tick(
    *,
    root: Path = DEFAULT_EVOLVE_ROOT,
    pr_port: PullRequestPort | None = None,
    git: GitPort | None = None,
    policy: MergePolicy | None = None,
    auto_merge: bool = False,
) -> str:
    """
    One organism worker tick: respect STOP, optionally merge last PR, reschedule.

    Returns a short status string for the CLI.
    """
    scheduler = FileScheduler(root=root)
    if scheduler.is_stopped():
        return "stopped"
    organism = ensure_organism(root=root)
    if organism.stopped:
        return "organism_stopped"

    status_parts: list[str] = ["awake"]
    if auto_merge and organism.last_run_id and pr_port is not None and git is not None:
        try:
            run = load_run(organism.last_run_id, root=root)
        except FileNotFoundError:
            run = None
        if run is not None and run.pr_url:
            ok, reason = try_auto_merge(
                pr_url=run.pr_url,
                pr_port=pr_port,
                git=git,
                policy=policy or MergePolicy(),
                organism=organism,
                changed_paths=list((policy or MergePolicy()).allowed_path_prefixes),
                diff_lines=0,
                scheduler=scheduler,
            )
            status_parts.append("merged" if ok else f"merge_skip:{reason}")
            save_organism(organism, root=root)

    schedule_next_wake(organism, root=root)
    logger.info("organism_tick status=%s", " ".join(status_parts))
    return " ".join(status_parts)
