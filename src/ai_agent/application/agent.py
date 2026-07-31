"""Agent facade — thin orchestrator over the tool loop."""

from __future__ import annotations

import logging

from aioconsole import ainput, aprint

from ai_agent.application.loop import LLMPort, run_tool_loop
from ai_agent.application.registry import ToolRegistry
from ai_agent.console_io import restore_blocking_stdio
from ai_agent.domain.models import AgentConfig, StepResult
from ai_agent.domain.state import ConversationState

logger = logging.getLogger(__name__)


class Agent:
    """
    Generic tool-using conversational agent.

    Responsibilities:
    - Own config + injected LLM + tool registry
    - Expose step() for runtime-driven I/O
    - Expose run() for standalone console sessions
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: LLMPort,
        registry: ToolRegistry,
        agent_id: str = "agent",
    ) -> None:
        self.agent_id = agent_id
        self.config = config
        self.llm = llm
        self.registry = registry

    def create_session(self) -> ConversationState:
        """Create an empty per-conversation session state."""
        return ConversationState()

    async def step(
        self,
        session: ConversationState,
        user_input: str | None,
    ) -> StepResult:
        """
        Execute one conversation turn (may include multiple tool rounds).

        Args:
            session: Mutable conversation state for this session.
            user_input: User message, or None to send the greeting.
        """
        try:
            result = await run_tool_loop(
                state=session,
                config=self.config,
                llm=self.llm,
                registry=self.registry,
                user_input=user_input,
            )
            logger.info(
                "agent_step agent_id=%s kind=%s rounds=%s",
                self.agent_id,
                result.kind,
                result.rounds_used,
            )
            return result
        except Exception as exc:
            logger.exception("agent_step_failed agent_id=%s", self.agent_id)
            session.mark_done()
            try:
                from ai_agent.application.self_harness import record_failure

                record_failure(
                    agent_id=self.agent_id,
                    message=str(exc),
                    tool_traces=[t.model_dump() for t in session.tool_traces],
                    context_summary=f"messages={len(session.messages)}",
                )
            except Exception:  # noqa: BLE001 — never block error path on logging
                logger.debug("failure_record_skipped", exc_info=True)
            return StepResult(
                message=f"Something went wrong: {exc}",
                kind="error",
                rounds_used=0,
            )

    async def run(self, session: ConversationState | None = None) -> None:
        """Standalone console loop (owns its own stdin/stdout)."""
        session = session or self.create_session()
        result = await self.step(session, user_input=None)
        # ainput leaves stdout non-blocking; restore before large writes.
        restore_blocking_stdio()
        await aprint(f"Assistant: {result.message}", flush=True)

        while not session.done:
            user_input = await ainput("You: ")
            result = await self.step(session, user_input=user_input)
            restore_blocking_stdio()
            await aprint(f"Assistant: {result.message}", flush=True)
            if result.kind in {"done", "error"}:
                break
