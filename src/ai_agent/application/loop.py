"""ReAct-style decide → act → observe loop (application use-case)."""

from __future__ import annotations

import json
import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel

from ai_agent.application.registry import ToolRegistry
from ai_agent.domain.models import AgentConfig, AgentDecision, Message, StepResult
from ai_agent.domain.state import ConversationState
from ai_agent.domain.tool import ToolResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMPort(Protocol):
    """Port the agent loop depends on — implemented in infrastructure."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        output_model: type[T],
    ) -> T:
        """Send chat messages and parse a structured response."""
        ...


def build_system_prompt(config: AgentConfig, registry: ToolRegistry) -> str:
    """Compose the system prompt with personality and available tool schemas."""
    tool_docs: list[dict[str, object]] = []
    for spec in registry.specs():
        params = {
            p.name: {
                "type": p.type,
                "description": p.description,
                "required": p.required,
            }
            for p in spec.parameters
        }
        tool_docs.append(
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": params,
            }
        )

    decision_schema = {
        "kind": "respond | call_tools | done",
        "message": "string — user-facing reply when kind is respond/done",
        "tool_calls": [{"name": "tool_name", "arguments": {"key": "value"}}],
    }

    return (
        f"{config.system_prompt}\n\n"
        f"Personality: tone={config.personality.tone}, style={config.personality.style}.\n\n"
        "You are a tool-using agent. On every turn reply with JSON matching this schema:\n"
        f"{json.dumps(decision_schema, indent=2)}\n\n"
        "Rules:\n"
        "- Use call_tools when a tool can compute or look up something more reliably than guessing.\n"
        "- Use respond when you can answer the user directly.\n"
        "- Use done when the user ends the conversation or the task is complete.\n"
        "- Never invent tool results — wait for tool observations.\n\n"
        f"Available tools:\n{json.dumps(tool_docs, indent=2)}"
    )


def _ensure_system_prompt(
    state: ConversationState,
    config: AgentConfig,
    registry: ToolRegistry,
) -> None:
    system = Message(role="system", content=build_system_prompt(config, registry))
    if state.messages and state.messages[0].role == "system":
        state.messages[0] = system
    else:
        state.messages.insert(0, system)


async def run_tool_loop(
    *,
    state: ConversationState,
    config: AgentConfig,
    llm: LLMPort,
    registry: ToolRegistry,
    user_input: str | None,
) -> StepResult:
    """
    Execute one user turn: optional greeting, then decide/act until respond/done.

    Bounded by config.max_tool_rounds to prevent runaway tool loops.
    """
    if not state.greeting_sent and user_input is None:
        greeting = config.greeting or "Hello! How can I help you today?"
        state.greeting_sent = True
        state.add_message("assistant", greeting)
        return StepResult(message=greeting, kind="respond", rounds_used=0)

    if user_input is not None:
        state.add_message("user", user_input)

    _ensure_system_prompt(state, config, registry)

    collected: list[ToolResult] = []

    for rounds in range(1, config.max_tool_rounds + 1):
        logger.info("agent_loop round=%s", rounds)
        decision = await llm.complete(state.as_chat_dicts(), AgentDecision)

        if decision.kind == "call_tools":
            if not decision.tool_calls:
                msg = "I tried to use a tool but received no tool calls. How else can I help?"
                state.add_message("assistant", msg)
                return StepResult(
                    message=msg,
                    kind="respond",
                    tool_results=[r.model_dump() for r in collected],
                    rounds_used=rounds,
                )

            observations: list[str] = []
            for call in decision.tool_calls:
                result = await registry.execute(call.name, call.arguments)
                collected.append(result)
                state.tool_traces.append(result)
                observations.append(
                    json.dumps(
                        {
                            "tool": result.tool_name,
                            "success": result.success,
                            "output": result.output,
                            "error": result.error,
                        }
                    )
                )
                logger.info(
                    "tool_executed name=%s success=%s",
                    result.tool_name,
                    result.success,
                )

            state.add_message("assistant", decision.model_dump_json())
            # Stored as domain role "tool"; as_chat_dicts() maps to user for the API.
            tool_label = (
                decision.tool_calls[0].name if len(decision.tool_calls) == 1 else "tools"
            )
            state.add_message("tool", "\n".join(observations), tool_name=tool_label)
            continue

        message = decision.message or ("Conversation complete." if decision.kind == "done" else "")
        state.add_message("assistant", message)
        if decision.kind == "done":
            state.mark_done()
            return StepResult(
                message=message,
                kind="done",
                tool_results=[r.model_dump() for r in collected],
                rounds_used=rounds,
            )

        return StepResult(
            message=message,
            kind="respond",
            tool_results=[r.model_dump() for r in collected],
            rounds_used=rounds,
        )

    fallback = "I reached the maximum number of tool rounds. Here is what I learned so far: " + (
        "; ".join(f"{r.tool_name}={r.output or r.error}" for r in collected)
        if collected
        else "no tool results."
    )
    state.add_message("assistant", fallback)
    logger.warning("max_tool_rounds_reached rounds=%s", config.max_tool_rounds)
    return StepResult(
        message=fallback,
        kind="respond",
        tool_results=[r.model_dump() for r in collected],
        rounds_used=config.max_tool_rounds,
    )
