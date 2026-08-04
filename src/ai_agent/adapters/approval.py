"""Human-in-the-loop approval adapters."""

from __future__ import annotations

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


class AutoApprovalGate:
    """Always approve — for tests and non-interactive briefs."""

    def __init__(self, *, approve: bool = True) -> None:
        self.approve = approve
        self.prompts: list[str] = []

    async def request(self, prompt: str) -> bool:
        self.prompts.append(prompt)
        logger.debug("auto_approval approve=%s prompt=%s", self.approve, prompt)
        return self.approve


class ConsoleApprovalGate:
    """Ask Y/n on stdin (serialized — never concurrent ainput)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def request(self, prompt: str) -> bool:
        from aioconsole import ainput

        from ai_agent.support.console_io import restore_blocking_stdio

        async with self._lock:
            print(f"\n[approval] {prompt}", file=sys.stderr, flush=True)
            try:
                answer = await ainput("Approve? [y/N]: ")
            except EOFError:
                logger.warning("approval_eof — treating as denied")
                return False
            finally:
                restore_blocking_stdio()
            return answer.strip().lower() in {"y", "yes"}
