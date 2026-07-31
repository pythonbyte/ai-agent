"""Human-in-the-loop approval adapters."""

from __future__ import annotations

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
    """Ask Y/n on stdin (aioconsole when available)."""

    async def request(self, prompt: str) -> bool:
        from aioconsole import ainput

        print(f"\n[approval] {prompt}", file=sys.stderr, flush=True)
        answer = await ainput("Approve? [y/N]: ")
        return answer.strip().lower() in {"y", "yes"}
