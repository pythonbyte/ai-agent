"""Evolve feature — survey → plan → edit → verify → HITL → PR."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ai_agent.domain.models import StepResult
from ai_agent.domain.platform import EvolveOrganism, EvolveRun
from ai_agent.domain.ports import ApprovalGate
from ai_agent.domain.state import ConversationState
from ai_agent.harness.agent import Agent
from ai_agent.harness.ops_metrics import emit_ops_event

logger = logging.getLogger(__name__)

DEFAULT_EVOLVE_ROOT = Path(".ai_agent/evolve")
DEFAULT_MAX_CONTINUE_TURNS = 10

EDIT_TOOLS = frozenset({"replace_in_file", "write_file", "apply_patch"})

EVOLVE_PROMPT_TEMPLATE = """You are running an evolve cycle for this repository.

Intent: {intent}
Run id: {run_id}
Artifact dir: {artifact_dir}

Interpret the intent carefully:
- Doc/README intents → EDIT README.md (allowlisted). Never open `.ai_agent/**`.
- Make ONE meaningful edit that matches the intent (not a tiny noop).

Strict pipeline — CALL TOOLS in order; do not narrate:
1. Survey: workspace_search action=search (or read with start_line/end_line).
2. Edit ONCE with replace_in_file (preferred). Do not call replace_in_file again
   after it succeeds.
3. VERIFY: git_diff (must be NON-EMPTY) then run_checks preset=pytest.
4. PUBLISH: git_commit alone (feature branch), then open_pull_request alone.
5. Respond with the PR URL only after open_pull_request succeeds.

If the requested text is already present and git_status is clean, respond that
the intent is already satisfied (no PR).
Never push to main. Never edit PathPolicy / MergePolicy / STOP / .env.
"""


@dataclass(frozen=True)
class PipelineProgress:
    """Deterministic progress derived from tool traces."""

    edited: bool
    diff_seen: bool
    checks_ok: bool
    committed: bool
    pr_opened: bool

    @property
    def next_action(self) -> str:
        if self.pr_opened:
            return "done"
        if self.committed:
            return "open_pull_request"
        if self.checks_ok:
            return "git_commit"
        if self.diff_seen:
            return "run_checks"
        if self.edited:
            return "git_diff"
        return "edit"


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


def pipeline_progress(tool_results: list[dict[str, object]]) -> PipelineProgress:
    edited = any(
        item.get("tool_name") in EDIT_TOOLS and item.get("success") for item in tool_results
    )
    diff_seen = False
    for item in tool_results:
        if item.get("tool_name") != "git_diff" or not item.get("success"):
            continue
        out = str(item.get("output") or "").strip()
        if out and out != "(empty diff)":
            diff_seen = True
    checks_ok = any(
        item.get("tool_name") == "run_checks" and item.get("success") for item in tool_results
    )
    committed = any(
        item.get("tool_name") == "git_commit" and item.get("success") for item in tool_results
    )
    pr_opened = any(
        item.get("tool_name") == "open_pull_request" and item.get("success")
        for item in tool_results
    )
    return PipelineProgress(
        edited=edited,
        diff_seen=diff_seen or committed or pr_opened,
        checks_ok=checks_ok or committed or pr_opened,
        committed=committed or pr_opened,
        pr_opened=pr_opened,
    )


def continue_prompt_for(progress: PipelineProgress) -> str:
    """State-aware nudge so evolve does not re-edit forever."""
    action = progress.next_action
    if action == "done":
        return "PR already opened. Respond with the PR URL only."
    if action == "open_pull_request":
        return (
            "CONTINUE: call open_pull_request ONLY (kind=call_tools). "
            "Do not edit files. Do not call replace_in_file again."
        )
    if action == "git_commit":
        return (
            "CONTINUE: call git_commit ONLY on a feature branch (kind=call_tools). "
            "Checks already passed. Do not edit files or re-run replace_in_file."
        )
    if action == "run_checks":
        return (
            "CONTINUE: call run_checks with preset=pytest ONLY. "
            "Diff already exists. Do not edit files again."
        )
    if action == "git_diff":
        return (
            "CONTINUE: edit already succeeded. Call git_diff then run_checks. "
            "Do NOT call replace_in_file/write_file/apply_patch again."
        )
    return (
        "CONTINUE: make the intent edit with replace_in_file ONCE, then git_diff, "
        "run_checks, git_commit, open_pull_request. Do not narrate."
    )


async def run_evolve(
    intent: str,
    *,
    agent: Agent,
    approval_gate: ApprovalGate | None = None,
    session: ConversationState | None = None,
    root: Path = DEFAULT_EVOLVE_ROOT,
    run_id: str | None = None,
    auto_write_plan: bool = True,
    max_continue_turns: int = DEFAULT_MAX_CONTINUE_TURNS,
) -> EvolveRun:
    """
    Run one engineer evolve cycle and persist a durable EvolveRun checkpoint.

    Continues the agent across multiple ``step`` turns until a PR URL appears,
    the agent reports a hard stop (clean tree / blocked), budget exhausts, or STOP.
    """
    _ = approval_gate
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
    collected: list[dict[str, object]] = []
    last_result: StepResult | None = None
    turns = max(1, max_continue_turns)

    try:
        for turn in range(turns):
            if is_stopped(root=root):
                run.status = "stopped"
                run.error = "STOP file present during evolve"
                save_run(run, root=root)
                emit_ops_event(name="evolve.stopped", run_id=rid, success=False)
                return run

            progress = pipeline_progress(collected)
            user_input = prompt if turn == 0 else continue_prompt_for(progress)
            if turn > 0:
                status_by_next: dict[
                    str,
                    Literal[
                        "editing",
                        "verifying",
                        "awaiting_approval",
                        "publishing",
                        "done",
                    ],
                ] = {
                    "edit": "editing",
                    "git_diff": "verifying",
                    "run_checks": "verifying",
                    "git_commit": "awaiting_approval",
                    "open_pull_request": "publishing",
                    "done": "done",
                }
                run.status = status_by_next.get(progress.next_action, "editing")
                save_run(run, root=root)

            result = await agent.step(session=session, user_input=user_input)
            last_result = result
            collected.extend(result.tool_results or [])
            progress = pipeline_progress(collected)
            logger.info(
                "evolve_turn run_id=%s turn=%s kind=%s next=%s msg=%s",
                rid,
                turn + 1,
                result.kind,
                progress.next_action,
                (result.message or "")[:200],
            )

            if result.kind == "error":
                run.status = "failed"
                run.error = result.message
                _write_result(artifact_dir, result, collected)
                save_run(run, root=root)
                emit_ops_event(
                    name="evolve.failed",
                    run_id=rid,
                    success=False,
                    detail=result.message[:300],
                )
                raise RuntimeError(result.message)

            pr_url = _extract_pr_url(result.message, collected)
            if pr_url or progress.pr_opened:
                latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
                run.pr_url = pr_url or _extract_pr_url("", collected)
                run.status = "done"
                run.error = None
                run.last_check_log = _last_check_log(collected)
                _write_result(artifact_dir, result, collected)
                save_run(run, root=root)
                emit_ops_event(
                    name="evolve.done",
                    run_id=rid,
                    success=True,
                    latency_ms=latency_ms,
                    detail=run.pr_url or "pr",
                )
                logger.info("evolve_complete run_id=%s status=done pr=%s", rid, run.pr_url)
                return run

            if _is_hard_stop(result.message, collected):
                break

            if turn + 1 < turns:
                run.fix_rounds = turn + 1
                save_run(run, root=root)
                continue
            break
    except Exception as exc:  # noqa: BLE001
        if run.status != "failed":
            run.status = "failed"
            run.error = str(exc)
            save_run(run, root=root)
            emit_ops_event(name="evolve.failed", run_id=rid, success=False, detail=str(exc))
        raise

    assert last_result is not None
    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    _write_result(artifact_dir, last_result, collected)
    progress = pipeline_progress(collected)
    if progress.committed:
        run.status = "awaiting_approval"
        run.error = "commit succeeded but open_pull_request did not run or failed"
        detail = "no_pr_after_commit"
    else:
        run.status = "failed"
        run.error = (
            f"incomplete pipeline (next={progress.next_action}): "
            f"{(last_result.message or 'no message')[:400]}"
        )
        detail = f"stuck_at_{progress.next_action}"
    run.last_check_log = _last_check_log(collected)
    save_run(run, root=root)
    emit_ops_event(
        name="evolve.incomplete",
        run_id=rid,
        success=False,
        latency_ms=latency_ms,
        detail=detail,
    )
    logger.info("evolve_complete run_id=%s status=%s pr=%s", rid, run.status, run.pr_url)
    return run


def _write_result(
    artifact_dir: Path,
    result: StepResult,
    collected: list[dict[str, object]],
) -> None:
    (artifact_dir / "result.json").write_text(
        json.dumps(
            {
                "kind": result.kind,
                "message": result.message,
                "rounds_used": result.rounds_used,
                "tool_results": collected,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _is_hard_stop(message: str, tool_results: list[dict[str, object]]) -> bool:
    """True when agent is blocked with evidence (clean tree / denied)."""
    text = (message or "").lower()

    if "denied by user" in text or "denied by the user" in text:
        return True
    for item in tool_results:
        err = str(item.get("error") or "").lower()
        if "denied by user" in err or "denied by the user" in err:
            return True

    git_clean = _git_status_is_clean(tool_results)
    satisfied_markers = (
        "nothing to commit",
        "already satisfied",
        "already documented",
        "already present",
        "no changes needed",
        "working tree clean",
        "intent is already",
    )
    if git_clean and any(m in text for m in satisfied_markers):
        return True

    for item in tool_results:
        err = str(item.get("error") or "").lower()
        if "nothing to commit" in err and git_clean:
            return True
    return False


def _git_status_is_clean(tool_results: list[dict[str, object]]) -> bool:
    for item in reversed(tool_results):
        if item.get("tool_name") != "git_status" or not item.get("success"):
            continue
        out = str(item.get("output") or "").strip().lower()
        return out in {"", "(clean)"}
    return False


def _tool_succeeded(tool_results: list[dict[str, object]] | None, name: str) -> bool:
    for item in tool_results or []:
        if item.get("tool_name") == name and item.get("success"):
            return True
    return False


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
