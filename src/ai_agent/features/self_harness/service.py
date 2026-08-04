"""Self-Harness scaffold — mine failures, propose patches, human-gated accept."""

from __future__ import annotations

import logging
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

from ai_agent.domain.harness_improve import FailureRecord, HarnessPatch

logger = logging.getLogger(__name__)

DEFAULT_FAILURES_DIR = Path(".ai_agent/failures")
DEFAULT_PROPOSALS_DIR = Path("proposals")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def record_failure(
    *,
    agent_id: str,
    message: str,
    tool_traces: list[dict[str, object]] | None = None,
    context_summary: str = "",
    failures_dir: Path = DEFAULT_FAILURES_DIR,
) -> FailureRecord:
    """Persist a failure record as JSON for later mining."""
    failures_dir.mkdir(parents=True, exist_ok=True)
    record = FailureRecord(
        id=_new_id("fail"),
        agent_id=agent_id,
        message=message,
        tool_traces=list(tool_traces or []),
        context_summary=context_summary,
    )
    path = failures_dir / f"{record.id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    logger.info("failure_recorded id=%s path=%s", record.id, path)
    return record


def load_failures(
    failures_dir: Path = DEFAULT_FAILURES_DIR,
    *,
    limit: int = 20,
) -> list[FailureRecord]:
    """Load recent failure records (newest first)."""
    if not failures_dir.is_dir():
        return []
    paths = sorted(failures_dir.glob("fail_*.json"), reverse=True)
    records: list[FailureRecord] = []
    for path in paths[: max(1, limit)]:
        records.append(FailureRecord.model_validate_json(path.read_text(encoding="utf-8")))
    return records


def mine_weaknesses(failures: list[FailureRecord]) -> list[str]:
    """
    Heuristic weakness mining (v0 — no clustering LLM).

    Returns short pattern strings derived from failure messages.
    """
    patterns: list[str] = []
    seen: set[str] = set()
    for failure in failures:
        key = failure.message.strip().lower()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        patterns.append(f"[{failure.agent_id}] {failure.message.strip()[:200]}")
    return patterns


def propose_harness_patch(
    failures: list[FailureRecord],
    *,
    proposals_dir: Path = DEFAULT_PROPOSALS_DIR,
) -> HarnessPatch:
    """
    Propose a minimal harness patch from mined failures (deterministic v0).

    A future version can call the LLM; v0 emits a safe prompt append + optional
    round bump so the loop is end-to-end without network.
    """
    patterns = mine_weaknesses(failures)
    if not patterns:
        raise ValueError("No failures to mine — record some with harness record-failure")

    bullet_list = "\n".join(f"- {p}" for p in patterns[:8])
    append = (
        "\n\n## Self-Harness notes (auto-proposed)\n"
        "When similar failures recur, prefer tools over guessing and cite sources.\n"
        f"Observed failure patterns:\n{bullet_list}\n"
    )
    patch = HarnessPatch(
        id=_new_id("patch"),
        summary=f"Address {len(patterns)} mined failure pattern(s)",
        system_prompt_append=append,
        max_tool_rounds=None,
        failure_ids=[f.id for f in failures[:8]],
        status="proposed",
    )
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"{patch.id}.json"
    path.write_text(patch.model_dump_json(indent=2), encoding="utf-8")
    logger.info("harness_patch_proposed id=%s path=%s", patch.id, path)
    return patch


def load_proposal(proposal_id: str, proposals_dir: Path = DEFAULT_PROPOSALS_DIR) -> HarnessPatch:
    path = proposals_dir / f"{proposal_id}.json"
    if not path.is_file():
        # Allow bare id or filename
        alt = proposals_dir / proposal_id
        if alt.is_file():
            path = alt
        else:
            raise FileNotFoundError(f"Proposal not found: {proposal_id}")
    return HarnessPatch.model_validate_json(path.read_text(encoding="utf-8"))


def run_validation_tests(*, pytest_args: list[str] | None = None) -> tuple[bool, str]:
    """Run a focused pytest subset; return (ok, output)."""
    args = pytest_args or [
        "tests/harness/test_tool_args.py",
        "tests/domain/test_agent_decision.py",
        "tests/features/brief/test_brief.py",
        "-q",
    ]
    completed = subprocess.run(  # noqa: S603 — intentional local test gate
        [sys.executable, "-m", "pytest", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, output


def accept_harness_patch(
    proposal_id: str,
    *,
    config_path: Path,
    proposals_dir: Path = DEFAULT_PROPOSALS_DIR,
    run_tests: bool = True,
) -> Path:
    """
    Validate (optional pytest) then merge allowed fields into agent YAML.

    Never edits arbitrary Python — only config surfaces listed on HarnessPatch.
    """
    patch = load_proposal(proposal_id, proposals_dir)
    if patch.status == "accepted":
        raise ValueError(f"Proposal already accepted: {proposal_id}")

    if run_tests:
        ok, output = run_validation_tests()
        if not ok:
            raise RuntimeError(f"Validation tests failed; refuse accept.\n{output[-2000:]}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping: {config_path}")

    if patch.system_prompt_append:
        existing = str(raw.get("system_prompt") or "")
        if patch.system_prompt_append.strip() not in existing:
            raw["system_prompt"] = existing.rstrip() + patch.system_prompt_append
    if patch.max_tool_rounds is not None:
        raw["max_tool_rounds"] = int(patch.max_tool_rounds)

    config_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    patch.status = "accepted"
    out = proposals_dir / f"{patch.id}.json"
    out.write_text(patch.model_dump_json(indent=2), encoding="utf-8")
    logger.info("harness_patch_accepted id=%s config=%s", patch.id, config_path)
    return config_path
