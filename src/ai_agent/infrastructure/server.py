"""WebSocket server adapter for multi-client agent sessions."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from ai_agent.application.agent import Agent
from ai_agent.domain.models import StepResult
from ai_agent.domain.ports import SessionStore
from ai_agent.orchestration.runtime import AgentRuntime

logger = logging.getLogger(__name__)


class WebSocketServer:
    """
    Infrastructure adapter: one WebSocket connection → one agent session.

    Keeps transport concerns out of the agent and runtime cores.
    """

    def __init__(
        self,
        agent_factory: Callable[[str], Agent],
        *,
        host: str = "localhost",
        port: int = 8765,
        session_store: SessionStore | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self.host = host
        self.port = port
        self.runtime = AgentRuntime(
            on_agent_output=self._on_output,
            session_store=session_store,
        )
        self._connections: dict[str, ServerConnection] = {}
        self._counter = 0

    def _on_output(self, agent_id: str, result: StepResult) -> None:
        connection = self._connections.get(agent_id)
        if connection is None:
            return
        asyncio.create_task(self._safe_send(connection, result.message))

    async def _safe_send(self, connection: ServerConnection, payload: str) -> None:
        try:
            await connection.send(payload)
        except Exception as exc:
            logger.warning("Failed to send WebSocket message: %s", exc)

    async def _handle(self, connection: ServerConnection) -> None:
        self._counter += 1
        agent_id = f"ws-{self._counter}"
        agent = self._agent_factory(agent_id)
        self._connections[agent_id] = connection
        self.runtime.register(agent_id, agent)
        task = await self.runtime.start_agent(agent_id)
        logger.info("WebSocket client connected as %s", agent_id)

        try:
            async for raw in connection:
                text = raw if isinstance(raw, str) else raw.decode("utf-8")
                data: Any
                try:
                    data = json.loads(text)
                    message = data.get("message", text) if isinstance(data, dict) else text
                except json.JSONDecodeError:
                    message = text
                await self.runtime.send_message(agent_id, str(message))
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected: %s", agent_id)
        finally:
            await self.runtime.stop_agent(agent_id)
            self.runtime.unregister(agent_id)
            self._connections.pop(agent_id, None)
            if not task.done():
                task.cancel()

    async def serve(self) -> None:
        async with websockets.serve(self._handle, self.host, self.port):
            logger.info("WebSocket server listening on ws://%s:%s", self.host, self.port)
            await asyncio.Future()
