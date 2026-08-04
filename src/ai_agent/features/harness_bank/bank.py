"""HarnessBank — Gene Bank I/O + gated screening (v1 stubs → full gates)."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from ai_agent.domain.platform import GeneCell, HarnessWhere, ScreeningResult

logger = logging.getLogger(__name__)

DEFAULT_GENE_BANK = Path(".ai_agent/gene_bank")

KERNEL_FORBIDDEN_PATHS: tuple[str, ...] = (
    "src/ai_agent/domain/path_policy.py",
    "src/ai_agent/domain/merge_policy.py",
    "src/ai_agent/domain/platform.py",
    ".ai_agent/evolve/STOP",
)


def cell_dir(where: HarnessWhere, why: str, *, root: Path = DEFAULT_GENE_BANK) -> Path:
    safe_why = re.sub(r"[^a-zA-Z0-9_-]+", "_", why.strip())[:80] or "unknown"
    path = root / f"{where}__{safe_why}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cell_id(where: HarnessWhere, why: str) -> str:
    return f"gene_{where}_{uuid.uuid4().hex[:8]}"


def save_cell(cell: GeneCell, *, root: Path = DEFAULT_GENE_BANK) -> Path:
    if not cell.id:
        cell.id = cell_id(cell.where, cell.why)
    directory = cell_dir(cell.where, cell.why, root=root)
    path = directory / "harness.json"
    # Keep history: also write id-stamped copy
    stamped = directory / f"{cell.id}.json"
    payload = cell.model_dump_json(indent=2)
    path.write_text(payload, encoding="utf-8")
    stamped.write_text(payload, encoding="utf-8")
    logger.info("gene_bank_saved id=%s where=%s why=%s", cell.id, cell.where, cell.why)
    return path


def load_cell(where: HarnessWhere, why: str, *, root: Path = DEFAULT_GENE_BANK) -> GeneCell | None:
    path = cell_dir(where, why, root=root) / "harness.json"
    if not path.is_file():
        return None
    return GeneCell.model_validate_json(path.read_text(encoding="utf-8"))


def list_cells(*, root: Path = DEFAULT_GENE_BANK) -> list[GeneCell]:
    if not root.is_dir():
        return []
    cells: list[GeneCell] = []
    for path in sorted(root.glob("*/harness.json")):
        cells.append(GeneCell.model_validate_json(path.read_text(encoding="utf-8")))
    return cells


def screen_candidate(
    cell: GeneCell,
    *,
    infra_ok: bool,
    activation_seen: bool,
    sample_score: float | None,
    parent_score: float | None,
    repeats_ok: bool = True,
    min_gain: float = 0.0,
    held_out_score: float | None = None,
) -> ScreeningResult:
    """
    Gated Harness Screening (deterministic):

    validity → activation → significance → gain (vs parent on sample).
    Held-out is recorded but not used for selection in v1 callers.
    """
    if not infra_ok:
        return ScreeningResult(
            passed=False,
            validity_ok=False,
            reason="infra failure — do not count",
        )
    if not activation_seen:
        return ScreeningResult(
            passed=False,
            validity_ok=True,
            activation_ok=False,
            reason="patch did not activate in trace",
        )
    if not repeats_ok:
        return ScreeningResult(
            passed=False,
            validity_ok=True,
            activation_ok=True,
            significance_ok=False,
            reason="significance/stability not met",
        )
    if sample_score is None or parent_score is None:
        return ScreeningResult(
            passed=False,
            validity_ok=True,
            activation_ok=True,
            significance_ok=True,
            gain_ok=False,
            reason="missing scores for gain gate",
            sample_score=sample_score,
            parent_score=parent_score,
        )
    gain_ok = sample_score - parent_score > min_gain
    # Held-out never used for selection — only advisory
    _ = held_out_score
    if not gain_ok:
        return ScreeningResult(
            passed=False,
            validity_ok=True,
            activation_ok=True,
            significance_ok=True,
            gain_ok=False,
            reason="no gain vs parent on sample set",
            sample_score=sample_score,
            parent_score=parent_score,
        )
    return ScreeningResult(
        passed=True,
        validity_ok=True,
        activation_ok=True,
        significance_ok=True,
        gain_ok=True,
        reason="admitted",
        sample_score=sample_score,
        parent_score=parent_score,
    )


def admit_if_screened(
    cell: GeneCell,
    screening: ScreeningResult,
    *,
    root: Path = DEFAULT_GENE_BANK,
) -> Path | None:
    """Persist cell only when screening passed. Kernel paths never written here."""
    if not screening.passed:
        logger.info("gene_bank_reject id=%s reason=%s", cell.id, screening.reason)
        return None
    cell.activation_seen = screening.activation_ok
    cell.train_score = screening.sample_score
    return save_cell(cell, root=root)


def assert_not_kernel_edit(relative_path: str) -> None:
    """Raise if evolver tries to touch immutable kernel paths."""
    normalized = relative_path.strip().replace("\\", "/")
    for forbidden in KERNEL_FORBIDDEN_PATHS:
        if normalized == forbidden or normalized.startswith(forbidden):
            raise PermissionError(f"evolver cannot modify kernel path: {normalized}")
