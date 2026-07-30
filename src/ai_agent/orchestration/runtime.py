"""Agent runtime — multi-agent orchestration with isolated queues."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from ai_agent.domain.models import StepResult
from ai_agent.domain.state import ConversationState

if TYPE_CHECKING:
    from ai_agent.application.agent import Agent

logger = logging.getLogger(__name__)


class MessageType(Enum):
    USER_INPUT = "user_input"
    SYSTEM = "system"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class RuntimeMessage:
    """Immutable message routed through the runtime."""

    sender: str
    recipient: str
    payload: str | None
    message_type: MessageType = MessageType.USER_INPUT


@dataclass
class AgentContext:
    """Isolated per-agent runtime context."""

    agent: Agent
    session: ConversationState
    inbox: asyncio.Queue[RuntimeMessage] = field(default_factory=asyncio.Queue)
    outbox: asyncio.Queue[tuple[str, StepResult]] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None
    active: bool = True


class AgentRuntime:
    """
    Orchestration layer: manages agent lifecycle and message routing.

    Agents remain pure logic — the runtime owns I/O loops and queues.
    """

    def __init__(
        self,
        on_agent_output: Callable[[str, StepResult], None] | None = None,
    ) -> None:
        self._contexts: dict[str, AgentContext] = {}
        self._on_agent_output = on_agent_output or self._default_output_handler
        self._running = False

    def _default_output_handler(self, agent_id: str, result: StepResult) -> None:
        print(f"[{agent_id}] Assistant: {result.message}")

    def register(self, agent_id: str, agent: Agent) -> asyncio.Queue[RuntimeMessage]:
        if agent_id in self._contexts:
            raise ValueError(f"Agent {agent_id} already registered")
        context = AgentContext(agent=agent, session=agent.create_session())
        self._contexts[agent_id] = context
        logger.info("Registered agent: %s", agent_id)
        return context.inbox

    def unregister(self, agent_id: str) -> None:
        if agent_id in self._contexts:
            del self._contexts[agent_id]
            logger.info("Unregistered agent: %s", agent_id)

    def get_inbox(self, agent_id: str) -> asyncio.Queue[RuntimeMessage]:
        return self._contexts[agent_id].inbox

    def get_outbox(self, agent_id: str) -> asyncio.Queue[tuple[str, StepResult]]:
        return self._contexts[agent_id].outbox

    def get_session(self, agent_id: str) -> ConversationState:
        if agent_id not in self._contexts:
            raise ValueError(f"Agent {agent_id} not found")
        return self._contexts[agent_id].session

    async def send_message(
        self,
        agent_id: str,
        message: str,
        sender: str = "user",
    ) -> None:
        if agent_id not in self._contexts:
            raise ValueError(f"Agent {agent_id} not found")
        msg = RuntimeMessage(sender=sender, recipient=agent_id, payload=message)
        await self._contexts[agent_id].inbox.put(msg)

    async def _run_agent_loop(self, agent_id: str) -> None:
        context = self._contexts[agent_id]
        agent = context.agent
        logger.info("Starting agent loop: %s", agent_id)

        try:
            result = await agent.step(session=context.session, user_input=None)
            context.outbox.put_nowait((agent_id, result))
            self._on_agent_output(agent_id, result)
        except Exception as exc:
            logger.error("[%s] Error on initial step: %s", agent_id, exc)

        while context.active and not context.session.done:
            try:
                msg = await context.inbox.get()
                if msg.message_type == MessageType.SHUTDOWN:
                    logger.info("[%s] Received shutdown signal", agent_id)
                    break

                result = await agent.step(
                    session=context.session,
                    user_input=msg.payload,
                )
                context.outbox.put_nowait((agent_id, result))
                self._on_agent_output(agent_id, result)

                if result.kind in {"done", "error"}:
                    break
            except asyncio.CancelledError:
                logger.info("[%s] Agent cancelled", agent_id)
                break
            except Exception as exc:
                logger.error("[%s] Error in agent loop: %s", agent_id, exc)
                context.session.mark_done()
                break

        self._save_session_report(agent_id, context.session)
        context.active = False
        logger.info("[%s] Agent loop ended", agent_id)

    def _save_session_report(self, agent_id: str, session: ConversationState) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"session_{agent_id}_{timestamp}.json"
        filepath = Path(tempfile.gettempdir()) / filename
        payload = {
            "agent_id": agent_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "done": session.done,
            "messages": [m.model_dump() for m in session.messages],
            "tool_traces": [t.model_dump() for t in session.tool_traces],
        }
        filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("[%s] Session report saved to: %s", agent_id, filepath)
        return filepath

    async def start_agent(self, agent_id: str) -> asyncio.Task[None]:
        if agent_id not in self._contexts:
            raise ValueError(f"Agent {agent_id} not registered")
        context = self._contexts[agent_id]
        context.task = asyncio.create_task(
            self._run_agent_loop(agent_id),
            name=f"agent-{agent_id}",
        )
        return context.task

    async def stop_agent(self, agent_id: str) -> None:
        if agent_id not in self._contexts:
            return
        context = self._contexts[agent_id]
        context.active = False
        shutdown = RuntimeMessage(
            sender="runtime",
            recipient=agent_id,
            payload=None,
            message_type=MessageType.SHUTDOWN,
        )
        await context.inbox.put(shutdown)
        if context.task and not context.task.done():
            context.task.cancel()
            try:
                await context.task
            except asyncio.CancelledError:
                pass

    async def run_all(self) -> None:
        self._running = True
        tasks = [await self.start_agent(agent_id) for agent_id in list(self._contexts)]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._running = False
        logger.info("All agents completed")

    async def shutdown(self) -> None:
        logger.info("Shutting down runtime...")
        self._running = False
        for agent_id in list(self._contexts):
            await self.stop_agent(agent_id)
