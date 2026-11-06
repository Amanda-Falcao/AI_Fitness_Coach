"""Model node and conditional routing logic, independent of LangGraph imports."""

import logging
from collections.abc import Callable
from typing import Any

from app.agent.state import AgentState


logger = logging.getLogger(__name__)


def create_agent_node(model_with_tools: Any) -> Callable[[AgentState], dict[str, list[Any]]]:
    """Create a graph node that appends one model response to the conversation."""
    def call_model(state: AgentState) -> dict[str, list[Any]]:
        messages = state.get("messages")
        if not messages:
            raise ValueError("Agent state must contain at least one message")
        response = model_with_tools.invoke(messages)
        logger.info("Agent model call completed")
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
