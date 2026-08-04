"""Tests for Gene Bank + gated screening."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.domain.platform import GeneCell
from ai_agent.features.harness_bank.bank import (
    admit_if_screened,
    assert_not_kernel_edit,
    list_cells,
    screen_candidate,
)


def test_screening_gates(tmp_path: Path) -> None:
    cell = GeneCell(
        where="prompt",
        why="timeout",
        model_id="m",
        summary="retry guidance",
        system_prompt_append="prefer tools",
    )
    fail = screen_candidate(
        cell,
        infra_ok=False,
        activation_seen=True,
        sample_score=1.0,
        parent_score=0.5,
    )
    assert not fail.passed

    fail = screen_candidate(
        cell,
        infra_ok=True,
        activation_seen=False,
        sample_score=1.0,
        parent_score=0.5,
    )
    assert not fail.passed

    fail = screen_candidate(
        cell,
        infra_ok=True,
        activation_seen=True,
        sample_score=0.4,
        parent_score=0.5,
    )
    assert not fail.passed

    ok = screen_candidate(
        cell,
        infra_ok=True,
        activation_seen=True,
        sample_score=0.8,
        parent_score=0.5,
    )
    assert ok.passed
    path = admit_if_screened(cell, ok, root=tmp_path)
    assert path is not None
    assert list_cells(root=tmp_path)


def test_kernel_edit_forbidden() -> None:
    with pytest.raises(PermissionError):
        assert_not_kernel_edit("src/ai_agent/domain/path_policy.py")
