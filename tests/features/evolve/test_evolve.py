"""Tests for evolve durable artifacts + STOP."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.domain.models import AgentDecision
from ai_agent.domain.platform import EvolveRun
from ai_agent.features.evolve.organism import ensure_organism, schedule_next_wake, worker_tick
from ai_agent.features.evolve.service import load_run, run_evolve, save_run
from tests.conftest import ScriptedLLM, make_agent


def test_save_load_run(tmp_path: Path) -> None:
    run = EvolveRun(id="evolve_test", intent="add tests", status="planned")
    save_run(run, root=tmp_path)
    loaded = load_run("evolve_test", root=tmp_path)
    assert loaded.intent == "add tests"


@pytest.mark.asyncio
async def test_run_evolve_persists(tmp_path: Path, sample_config) -> None:
    sample_config.tools = ["calculator"]
    llm = ScriptedLLM(
        [AgentDecision(kind="respond", message="Done without PR")]
    )
    agent = make_agent(sample_config, llm)
    run = await run_evolve("improve docs", agent=agent, root=tmp_path)
    assert run.status == "done"
    assert (tmp_path / run.id / "run.json").is_file()
    assert (tmp_path / run.id / "plan.md").is_file()


@pytest.mark.asyncio
async def test_stop_blocks_evolve(tmp_path: Path, sample_config) -> None:
    (tmp_path / "STOP").write_text("halt\n", encoding="utf-8")
    llm = ScriptedLLM([])
    agent = make_agent(sample_config, llm)
    with pytest.raises(RuntimeError, match="STOP"):
        await run_evolve("x", agent=agent, root=tmp_path)


def test_organism_worker_respects_stop(tmp_path: Path) -> None:
    ensure_organism(root=tmp_path)
    (tmp_path / "STOP").write_text("1", encoding="utf-8")
    assert worker_tick(root=tmp_path) == "stopped"


def test_schedule_wake(tmp_path: Path) -> None:
    organism = ensure_organism(root=tmp_path, goals=["ship"])
    schedule_next_wake(organism, root=tmp_path, hours=1.0)
    assert organism.next_wake_at
    assert (tmp_path / "next_wake.json").is_file()
