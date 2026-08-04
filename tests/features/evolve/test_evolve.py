"""Tests for evolve durable artifacts + STOP."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agent.domain.models import AgentDecision
from ai_agent.domain.platform import EvolveRun
from ai_agent.features.evolve.organism import ensure_organism, schedule_next_wake, worker_tick
from ai_agent.features.evolve.service import (
    continue_prompt_for,
    load_run,
    pipeline_progress,
    run_evolve,
    save_run,
)
from tests.conftest import ScriptedLLM, make_agent


def test_save_load_run(tmp_path: Path) -> None:
    run = EvolveRun(id="evolve_test", intent="add tests", status="planned")
    save_run(run, root=tmp_path)
    loaded = load_run("evolve_test", root=tmp_path)
    assert loaded.intent == "add tests"


def test_pipeline_progress_and_continue_prompt() -> None:
    progress = pipeline_progress([])
    assert progress.next_action == "edit"
    assert "replace_in_file" in continue_prompt_for(progress)

    progress = pipeline_progress(
        [{"tool_name": "replace_in_file", "success": True, "output": "ok", "error": None}]
    )
    assert progress.next_action == "git_diff"
    assert "Do NOT call replace_in_file" in continue_prompt_for(progress)

    progress = pipeline_progress(
        [
            {"tool_name": "replace_in_file", "success": True, "output": "ok", "error": None},
            {"tool_name": "git_diff", "success": True, "output": "diff --git", "error": None},
            {"tool_name": "run_checks", "success": True, "output": "ok", "error": None},
        ]
    )
    assert progress.next_action == "git_commit"
    assert "git_commit ONLY" in continue_prompt_for(progress)


@pytest.mark.asyncio
async def test_run_evolve_persists(tmp_path: Path, sample_config) -> None:
    sample_config.tools = ["calculator"]
    llm = ScriptedLLM(
        [
            AgentDecision(
                kind="respond",
                message="Intent already satisfied — nothing to commit",
            )
        ]
    )
    agent = make_agent(sample_config, llm)
    # Without a clean git_status tool result, narration alone should continue
    # until budget, then fail — use max_continue_turns=1 for a quick fail path.
    run = await run_evolve(
        "improve docs",
        agent=agent,
        root=tmp_path,
        max_continue_turns=1,
    )
    assert run.status == "failed"
    assert run.pr_url is None
    assert (tmp_path / run.id / "run.json").is_file()
    assert (tmp_path / run.id / "plan.md").is_file()


@pytest.mark.asyncio
async def test_run_evolve_continues_after_narration(tmp_path: Path, sample_config) -> None:
    sample_config.tools = ["calculator"]
    llm = ScriptedLLM(
        [
            AgentDecision(kind="respond", message="Plan saved. Proceeding to apply the patch."),
            AgentDecision(kind="respond", message="Still editing…"),
            AgentDecision(kind="respond", message="Giving up without a PR"),
        ]
    )
    agent = make_agent(sample_config, llm)
    run = await run_evolve(
        "add note",
        agent=agent,
        root=tmp_path,
        max_continue_turns=3,
    )
    assert run.status == "failed"
    assert len(llm.calls) >= 2


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
