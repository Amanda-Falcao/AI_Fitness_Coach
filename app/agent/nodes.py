"""Model node and conditional routing logic, independent of LangGraph imports."""

import logging
from collections.abc import Callable
from typing import Any

from app.agent.state import AgentState
from app.agent.plan_output import groq_plan_response_format


logger = logging.getLogger(__name__)


def create_agent_node(
    model_with_tools: Any, *, final_model: Any | None = None
) -> Callable[[AgentState], dict[str, list[Any]]]:
    """Create a model node, switching to a no-tools JSON model after RAG returns."""
    def call_model(state: AgentState) -> dict[str, list[Any]]:
        messages = state.get("messages")
        if not messages:
            raise ValueError("Agent state must contain at least one message")
        has_rag_result = any(
            getattr(message, "type", None) == "tool"
            and getattr(message, "name", None) == "fitness_knowledge_base_search"
            for message in messages
        )
        is_final_call = has_rag_result and final_model is not None
        selected_model = final_model if is_final_call else model_with_tools
        if is_final_call:
            frequency = state.get("sessions_per_week")
            if isinstance(frequency, bool) or not isinstance(frequency, int):
                raise ValueError("Agent state must include sessions_per_week for final plan generation")
            selected_model = final_model.bind(
                response_format=groq_plan_response_format(frequency)
            )
        response = selected_model.invoke(messages)
        logger.info(
            "Agent model call completed",
            extra={
                "event": "agent.model_call_completed",
                "stage": "final_json" if is_final_call else "tool_selection",
            },
        )
        return {"messages": [response]}

    return call_model


def route_after_agent(state: AgentState) -> str:
    """Route tool requests to the tool node; otherwise finish the graph."""
    messages = state.get("messages")
    if not messages:
        raise ValueError("Agent state must contain at least one message")
    if getattr(messages[-1], "tool_calls", None):
        return "tools"
    return "end"
