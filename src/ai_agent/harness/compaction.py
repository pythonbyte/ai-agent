"""Context compaction — pack long histories without discarding meaning."""

from __future__ import annotations

import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

from ai_agent.domain.models import CompactionConfig, Message
from ai_agent.domain.ports import PackedContext
from ai_agent.domain.state import ConversationState

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

SUMMARY_PREFIX = "[Compacted context — earlier turns summarized]"


class ContextSummary(BaseModel):
    """Structured LLM output for a compaction summary."""

    summary: str = Field(min_length=1)


class LLMPort(Protocol):
    """Minimal LLM surface used by the summarizing packer (mirrors harness.loop)."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        output_model: type[T],
    ) -> T: ...


def estimate_chars(messages: list[dict[str, str]]) -> int:
    """Cheap stand-in for tokens: total character length of role+content."""
    total = 0
    for message in messages:
        total += len(message.get("role", "")) + len(message.get("content", ""))
    return total


def needs_compaction(*, enabled: bool, char_count: int, max_context_chars: int) -> bool:
    """Return True when packing should summarize older turns."""
    if not enabled:
        return False
    if max_context_chars < 1:
        return False
    return char_count > max_context_chars


def split_messages(
    messages: list[Message],
    *,
    keep_recent: int,
) -> tuple[Message | None, list[Message], list[Message]]:
    """
    Split into system (optional), old middle, and recent tail.

    Guardrails:
    - system message (index 0 if role=system) is always separated
    - keep_recent is clamped to at least 1
    - if history is short, old is empty
    """
    if keep_recent < 1:
        raise ValueError("keep_recent must be >= 1")

    if not messages:
        return None, [], []

    system: Message | None = None
    body = list(messages)
    if body[0].role == "system":
        system = body[0]
        body = body[1:]

    if len(body) <= keep_recent:
        return system, [], body

    old = body[:-keep_recent]
    recent = body[-keep_recent:]
    return system, old, recent


def clamp_summary(text: str, *, max_chars: int) -> str:
    """Bound summary length; empty input becomes a stable placeholder."""
    cleaned = text.strip()
    if not cleaned:
        return "(no earlier context)"
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 15].rstrip() + "\n...[truncated]"


def deterministic_summary(messages: list[Message], *, max_chars: int) -> str:
    """
    Fallback when the summarizer LLM fails — preserve role-tagged snippets.

    Prefer this over silent truncation of the entire middle.
    """
    lines: list[str] = []
    for message in messages:
        snippet = message.content.strip().replace("\n", " ")
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."
        label = message.tool_name or message.role
        lines.append(f"- {label}: {snippet}")
    return clamp_summary("\n".join(lines), max_chars=max_chars)


def build_wire_messages(
    *,
    system: Message | None,
    summary: str | None,
    recent: list[Message],
) -> list[dict[str, str]]:
    """Assemble chat-dicts for the LLM from packed parts."""
    out: list[dict[str, str]] = []
    if system is not None:
        out.append({"role": "system", "content": system.content})
    if summary is not None:
        out.append(
            {
                "role": "user",
                "content": f"{SUMMARY_PREFIX}\n{summary}",
            }
        )
    for message in recent:
        if message.role == "tool":
            label = message.tool_name or "tool"
            out.append(
                {
                    "role": "user",
                    "content": f"[Observation from {label}]\n{message.content}",
                }
            )
        else:
            out.append({"role": message.role, "content": message.content})
    return out


class PassThroughPacker:
    """No-op packer — always returns full history (tests / disable path)."""

    async def pack(
        self,
        state: ConversationState,
        *,
        budget: CompactionConfig,
    ) -> PackedContext:
        wire = state.as_chat_dicts()
        chars = estimate_chars(wire)
        return PackedContext(
            messages=wire,
            compacted=False,
            original_chars=chars,
            packed_chars=chars,
        )


class SummarizingCompactor:
    """
    ContextPacker that summarizes old turns when over budget.

    Full ``ConversationState.messages`` is left intact; only the wire view shrinks.
    """

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def pack(
        self,
        state: ConversationState,
        *,
        budget: CompactionConfig,
    ) -> PackedContext:
        full_wire = state.as_chat_dicts()
        original_chars = estimate_chars(full_wire)

        if not needs_compaction(
            enabled=budget.enabled,
            char_count=original_chars,
            max_context_chars=budget.max_context_chars,
        ):
            return PackedContext(
                messages=full_wire,
                compacted=False,
                summary=state.context_summary,
                original_chars=original_chars,
                packed_chars=original_chars,
            )

        system, old, recent = split_messages(
            state.messages,
            keep_recent=budget.keep_recent_messages,
        )
        if not old:
            # Over budget but nothing eligible to summarize — send as-is.
            return PackedContext(
                messages=full_wire,
                compacted=False,
                summary=state.context_summary,
                original_chars=original_chars,
                packed_chars=original_chars,
            )

        summary = await self._summarize_old(old, budget=budget)
        state.context_summary = summary
        wire = build_wire_messages(system=system, summary=summary, recent=recent)
        packed_chars = estimate_chars(wire)
        logger.info(
            "context_compacted original_chars=%s packed_chars=%s old_messages=%s",
            original_chars,
            packed_chars,
            len(old),
        )
        return PackedContext(
            messages=wire,
            compacted=True,
            summary=summary,
            original_chars=original_chars,
            packed_chars=packed_chars,
        )

    async def _summarize_old(
        self,
        old: list[Message],
        *,
        budget: CompactionConfig,
    ) -> str:
        transcript = deterministic_summary(old, max_chars=budget.max_summary_chars * 2)
        prompt = (
            "Summarize the following agent conversation history for future turns. "
            "Preserve: goals, constraints, key facts, tool outcomes, and open tasks. "
            "Omit chit-chat. Return JSON with a single string field `summary`.\n\n"
            f"{transcript}"
        )
        try:
            result = await self._llm.complete(
                [{"role": "user", "content": prompt}],
                ContextSummary,
            )
            return clamp_summary(result.summary, max_chars=budget.max_summary_chars)
        except Exception:  # noqa: BLE001 — never fail the agent turn on compaction
            logger.warning("compaction_summarize_failed; using deterministic summary", exc_info=True)
            return deterministic_summary(old, max_chars=budget.max_summary_chars)
