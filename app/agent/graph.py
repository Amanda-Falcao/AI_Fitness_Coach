"""LangGraph construction with injected model and tools."""

from collections.abc import Sequence
from typing import Any

from app.agent.nodes import create_agent_node, route_after_agent
from app.agent.state import AgentState


DEFAULT_RECURSION_LIMIT = 12


def create_agent_graph(model: Any, tools: Sequence[Any], *, checkpointer: Any = None):
    """Bind tools and compile the model/tool loop as a LangGraph application."""
    if not tools:
        raise ValueError("At least one tool is required to build the agent graph")
    try:
        from langgraph.graph import END, StateGraph
        from langgraph.prebuilt import ToolNode
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph dependencies are missing; install the project requirements"
        ) from exc

    model_with_tools = model.bind_tools(list(tools))
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", create_agent_node(model_with_tools))
    workflow.add_node("tools", ToolNode(list(tools)))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "end": END},
    )
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=checkpointer)
