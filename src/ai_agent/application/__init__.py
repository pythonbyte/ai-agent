"""Application layer — agent use-cases and tool registry."""

from ai_agent.application.agent import Agent
from ai_agent.application.brief import run_research_brief
from ai_agent.application.loop import LLMPort, build_system_prompt, run_tool_loop
from ai_agent.application.registry import ToolRegistry
from ai_agent.application.self_harness import (
    accept_harness_patch,
    propose_harness_patch,
    record_failure,
)
from ai_agent.application.tool_args import ArgValidationResult, validate_tool_arguments

__all__ = [
    "Agent",
    "ArgValidationResult",
    "LLMPort",
    "ToolRegistry",
    "accept_harness_patch",
    "build_system_prompt",
    "propose_harness_patch",
    "record_failure",
    "run_research_brief",
    "run_tool_loop",
    "validate_tool_arguments",
]
