"""Evolve feature — survey → plan → edit → verify → HITL → PR."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ai_agent.domain.platform import EvolveOrganism, EvolveRun
from ai_agent.domain.ports import ApprovalGate
from ai_agent.domain.state import ConversationState
from ai_agent.harness.agent import Agent
from ai_agent.harness.ops_metrics import emit_ops_event

logger = logging.getLogger(__name__)

DEFAULT_EVOLVE_ROOT = Path(".ai_agent/evolve")

EVOLVE_PROMPT_TEMPLATE = """You are running an evolve cycle for this repository.

Intent: {intent}
Run id: {run_id}
Artifact dir: {artifact_dir}

Durable checklist (follow in order):
1. Survey the workspace (workspace_list / workspace_search / git_status).
2. Write plan.md under the artifact dir by describing the plan clearly in your
   working notes; include paths to touch and how you will verify.
3. Apply small unified diffs via apply_patch (allowlisted paths only).
4. run_checks until green (or report failure after bounded attempts).
5. When green: git_commit then open_pull_request (both need human approval).
6. Final respond must include the PR URL if opened, else a clear status summary.

Do not push to main. Do not edit PathPolicy / MergePolicy / STOP / .env.
"""


def new_run_id() -> str:
    return f"evolve_{uuid.uuid4().hex[:10]}"


def slugify_intent(intent: str, *, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", intent.strip().lower()).strip("-")
    if not cleaned:
        cleaned = "intent"
    return cleaned[:max_len].rstrip("-")


def run_dir(root: Path, run_id: str) -> Path:
    path = root / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_run(run: EvolveRun, *, root: Path = DEFAULT_EVOLVE_ROOT) -> Path:
    directory = run_dir(root, run.id)
    path = directory / "run.json"
    run.updated_at = datetime.now(UTC).isoformat()
    path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_run(run_id: str, *, root: Path = DEFAULT_EVOLVE_ROOT) -> EvolveRun:
    path = root / run_id / "run.json"
    if not path.is_file():
        raise FileNotFoundError(f"evolve run not found: {path}")
    return EvolveRun.model_validate_json(path.read_text(encoding="utf-8"))


def save_organism(organism: EvolveOrganism, *, root: Path = DEFAULT_EVOLVE_ROOT) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "organism.json"
    path.write_text(organism.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_organism(*, root: Path = DEFAULT_EVOLVE_ROOT) -> EvolveOrganism | None:
    path = root / "organism.json"
    if not path.is_file():
        return None
    return EvolveOrganism.model_validate_json(path.read_text(encoding="utf-8"))


def write_plan(artifact_dir: Path, intent: str, plan_body: str) -> Path:
    path = artifact_dir / "plan.md"
    body = f"# Evolve plan\n\nIntent: {intent}\n\n{plan_body.strip()}\n"
    path.write_text(body, encoding="utf-8")
    return path


def is_stopped(*, root: Path = DEFAULT_EVOLVE_ROOT) -> bool:
    return (root / "STOP").is_file()


async def run_evolve(
    intent: str,
    *,
    agent: Agent,
    approval_gate: ApprovalGate | None = None,
    session: ConversationState | None = None,
    root: Path = DEFAULT_EVOLVE_ROOT,
    run_id: str | None = None,
    auto_write_plan: bool = True,
) -> EvolveRun:
    """
    Run one engineer evolve cycle and persist a durable EvolveRun checkpoint.

    Phase 1: HITL before commit/PR (tools gate via ApprovalGate).
    """
    cleaned = intent.strip()
    if not cleaned:
        raise ValueError("intent must be non-empty")
    if is_stopped(root=root):
        raise RuntimeError("evolve STOP file present; refusing to start")

    rid = run_id or new_run_id()
    artifact_dir = run_dir(root, rid)
    run = EvolveRun(id=rid, intent=cleaned, status="planned", plan_path=None)
    if auto_write_plan:
        plan_path = write_plan(
            artifact_dir,
            cleaned,
            "Agent will refine this plan during the survey step.",
        )
        run.plan_path = str(plan_path)
    save_run(run, root=root)
    emit_ops_event(name="evolve.start", run_id=rid, detail=cleaned[:200])

    session = session or agent.create_session()
    session.greeting_sent = True

    run.status = "editing"
    save_run(run, root=root)

    prompt = EVOLVE_PROMPT_TEMPLATE.format(
        intent=cleaned,
        run_id=rid,
        artifact_dir=str(artifact_dir),
    )
    started = datetime.now(UTC)
    try:
        result = await agent.step(session=session, user_input=prompt)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = str(exc)
        save_run(run, root=root)
        emit_ops_event(name="evolve.failed", run_id=rid, success=False, detail=str(exc))
        raise

    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    (artifact_dir / "result.json").write_text(
        json.dumps(
            {
                "kind": result.kind,
                "message": result.message,
                "rounds_used": result.rounds_used,
                "tool_results": result.tool_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if result.kind == "error":
        run.status = "failed"
        run.error = result.message
        save_run(run, root=root)
        emit_ops_event(
            name="evolve.failed",
            run_id=rid,
            success=False,
            latency_ms=latency_ms,
            detail=result.message[:300],
        )
        raise RuntimeError(result.message)

    pr_url = _extract_pr_url(result.message, result.tool_results)
    if pr_url:
        run.pr_url = pr_url
        run.status = "done"
    else:
        # May still be awaiting approval or stopped mid-cycle
        run.status = "done"
    run.last_check_log = _last_check_log(result.tool_results)
    save_run(run, root=root)
    emit_ops_event(
        name="evolve.done",
        run_id=rid,
        success=True,
        latency_ms=latency_ms,
        detail=pr_url or "no_pr",
    )
    logger.info("evolve_complete run_id=%s status=%s pr=%s", rid, run.status, run.pr_url)
    return run


def _extract_pr_url(message: str, tool_results: list[dict[str, object]] | None) -> str | None:
    for item in tool_results or []:
        if item.get("tool_name") == "open_pull_request" and item.get("success"):
            out = str(item.get("output") or "")
            if out.startswith("http"):
                return out.strip()
    match = re.search(r"https://github\.com/[^\s)]+", message)
    if match:
        return match.group(0)
    return None


def _last_check_log(tool_results: list[dict[str, object]] | None) -> str:
    for item in reversed(tool_results or []):
        if item.get("tool_name") == "run_checks":
            return str(item.get("output") or item.get("error") or "")[:4000]
    return ""
