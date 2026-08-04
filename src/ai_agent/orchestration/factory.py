"""Agent factory — build agents from role YAML templates."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ai_agent.adapters.config_loader import load_agent_config
from ai_agent.adapters.llm import OpenRouterLLM
from ai_agent.domain.ports import AgentMessenger, ApprovalGate
from ai_agent.harness.agent import Agent
from ai_agent.harness.registry import ToolRegistry
from ai_agent.tools import build_default_registry

RoleFactory = Callable[[str], Agent]


class AgentFactory:
    """
    Create agents from ``config/agents/{role}.yaml`` templates.

    Used by dynamic ``spawn_agent`` so the runtime is not limited to
    statically registered personas.
    """

    def __init__(
        self,
        *,
        agents_dir: Path | str = Path("config/agents"),
        messenger: AgentMessenger | None = None,
        approval_gate: ApprovalGate | None = None,
        registry_base: ToolRegistry | None = None,
    ) -> None:
        self.agents_dir = Path(agents_dir)
        self._messenger = messenger
        self._approval_gate = approval_gate
        self._registry_base = registry_base

    def role_path(self, role: str) -> Path:
        safe = role.strip().replace("..", "").replace("/", "_")
        path = self.agents_dir / f"{safe}.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"Unknown agent role config: {path}")
        return path

    def create(
        self,
        role: str,
        *,
        agent_id: str,
        messenger_sender_id: str | None = None,
    ) -> Agent:
        config = load_agent_config(self.role_path(role))
        registry = self._registry_base or build_default_registry(
            workspace_root=config.workspace_root,
            messenger=self._messenger,
            messenger_sender_id=messenger_sender_id or agent_id,
            approval_gate=self._approval_gate,
            include_engineer_tools=bool(
                set(config.tools or [])
                & {
                    "workspace_list",
                    "apply_patch",
                    "write_file",
                    "run_checks",
                    "git_status",
                    "git_diff",
                    "git_commit",
                    "open_pull_request",
                }
            ),
        )
        if self._messenger is not None and not registry.has("message_agent"):
            from ai_agent.tools.message_agent import MessageAgentTool

            registry.register(
                MessageAgentTool(self._messenger, sender_id=messenger_sender_id or agent_id)
            )
        if self._messenger is not None and not registry.has("spawn_agent"):
            # Spawn tool is registered by runtime when factory is bound.
            pass
        selected = registry.select(config.tools) if config.tools else registry
        llm = OpenRouterLLM(model=config.model)
        return Agent(config=config, llm=llm, registry=selected, agent_id=agent_id)
