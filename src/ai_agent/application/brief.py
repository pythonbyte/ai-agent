"""Research brief use-case — run the operator once and persist markdown."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from ai_agent.application.agent import Agent
from ai_agent.domain.models import StepResult
from ai_agent.domain.ports import ApprovalGate
from ai_agent.domain.state import ConversationState

logger = logging.getLogger(__name__)

BRIEF_PROMPT_TEMPLATE = """Produce a research brief on the following topic.

Topic: {topic}

Requirements:
- Use tools (web_search, http_get, retrieve, workspace_search) as needed.
- Do not invent sources.
- Final respond message MUST be markdown with these sections:
  ## Summary
  ## Key findings
  ## Sources
  ## Open questions
"""


def slugify(topic: str, *, max_len: int = 60) -> str:
    """Filesystem-safe slug from a research topic."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", topic.strip().lower()).strip("-")
    if not cleaned:
        cleaned = "brief"
    return cleaned[:max_len].rstrip("-")


def render_brief_markdown(
    topic: str,
    result: StepResult,
    *,
    include_tool_traces: bool = True,
) -> str:
    """Compose the on-disk brief from the agent step result."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        f"# Research brief: {topic}",
        "",
        f"_Generated {stamp} · rounds={result.rounds_used} · kind={result.kind}_",
        "",
        result.message.strip() or "(empty response)",
        "",
    ]
    if include_tool_traces and result.tool_results:
        parts.extend(
            [
                "## Tool traces",
                "",
                "```json",
                json.dumps(result.tool_results, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(parts)


async def run_research_brief(
    topic: str,
    *,
    agent: Agent,
    session: ConversationState | None = None,
    output_dir: Path,
    approval_gate: ApprovalGate | None = None,
    require_approval: bool = False,
) -> Path:
    """
    Run one operator turn for ``topic`` and write a markdown brief.

    When ``require_approval`` is True, asks ``approval_gate`` before writing.
    """
    cleaned = topic.strip()
    if not cleaned:
        raise ValueError("topic must be non-empty")

    session = session or agent.create_session()
    # Skip deterministic greeting for one-shot briefs.
    session.greeting_sent = True

    prompt = BRIEF_PROMPT_TEMPLATE.format(topic=cleaned)
    result = await agent.step(session=session, user_input=prompt)

    if result.kind == "error":
        raise RuntimeError(result.message)

    if require_approval:
        if approval_gate is None:
            raise ValueError("require_approval=True needs an ApprovalGate")
        approved = await approval_gate.request(
            f"Publish research brief on {cleaned!r} to {output_dir}?"
        )
        if not approved:
            raise PermissionError("Brief publication declined by user")

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    path = output_dir / f"{stamp}_{slugify(cleaned)}.md"
    path.write_text(render_brief_markdown(cleaned, result), encoding="utf-8")
    logger.info("research_brief_written path=%s", path)
    return path
