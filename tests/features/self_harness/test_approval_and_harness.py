"""Tests for request_approval tool and Self-Harness scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_agent.adapters.approval import AutoApprovalGate
from ai_agent.features.self_harness.service import (
    accept_harness_patch,
    load_failures,
    mine_weaknesses,
    propose_harness_patch,
    record_failure,
)
from ai_agent.harness.registry import ToolRegistry
from ai_agent.tools.request_approval import RequestApprovalTool


@pytest.mark.asyncio
async def test_request_approval_allow_and_deny() -> None:
    allow = AutoApprovalGate(approve=True)
    deny = AutoApprovalGate(approve=False)
    ok = RequestApprovalTool(allow)
    no = RequestApprovalTool(deny)

    approved = await ok.execute({"reason": "publish brief"})
    assert approved.success is True
    assert approved.output == "approved"

    rejected = await no.execute({"reason": "delete everything"})
    assert rejected.success is False
    assert "denied" in (rejected.error or "")


@pytest.mark.asyncio
async def test_registry_wires_approval() -> None:
    gate = AutoApprovalGate(approve=True)
    registry = ToolRegistry()
    registry.register(RequestApprovalTool(gate))
    result = await registry.execute("request_approval", {"reason": "ship it"})
    assert result.success is True


def test_self_harness_propose_and_accept(tmp_path: Path) -> None:
    failures_dir = tmp_path / "failures"
    proposals_dir = tmp_path / "proposals"
    record_failure(
        agent_id="operator",
        message="LLM failed: kind must be call_tools",
        failures_dir=failures_dir,
    )
    record_failure(
        agent_id="operator",
        message="Timed out waiting for researcher",
        failures_dir=failures_dir,
    )
    failures = load_failures(failures_dir, limit=10)
    assert len(failures) == 2
    patterns = mine_weaknesses(failures)
    assert patterns

    patch = propose_harness_patch(failures, proposals_dir=proposals_dir)
    assert patch.status == "proposed"
    assert (proposals_dir / f"{patch.id}.json").is_file()

    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": "openai/gpt-4o-mini",
                "system_prompt": "You are helpful.",
                "max_tool_rounds": 5,
                "tools": ["web_search"],
            }
        ),
        encoding="utf-8",
    )
    accept_harness_patch(
        patch.id,
        config_path=config_path,
        proposals_dir=proposals_dir,
        run_tests=False,
    )
    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "Self-Harness notes" in updated["system_prompt"]
