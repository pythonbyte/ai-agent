"""
ai-agent — a small, typed, tool-using conversational agent kit.

Clean architecture layers:
  domain → application → infrastructure / orchestration / tools / cli
"""

from ai_agent.application.agent import Agent
from ai_agent.application.registry import ToolRegistry
from ai_agent.domain.models import AgentConfig, Personality, StepResult
from ai_agent.domain.state import ConversationState
from ai_agent.domain.tool import BaseTool, Tool, ToolParameter, ToolResult
from ai_agent.infrastructure.config_loader import load_agent_config
from ai_agent.infrastructure.llm import OpenRouterLLM
from ai_agent.orchestration.runtime import AgentRuntime
from ai_agent.tools import build_default_registry

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentRuntime",
    "BaseTool",
    "ConversationState",
    "OpenRouterLLM",
    "Personality",
    "StepResult",
    "Tool",
    "ToolParameter",
    "ToolRegistry",
    "ToolResult",
    "build_default_registry",
    "load_agent_config",
]

__version__ = "0.1.0"
