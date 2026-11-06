"""State contract shared by the LangGraph nodes."""

from operator import add
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    """Conversation messages accumulated across the agent/tool loop."""

    messages: Annotated[list[Any], add]
