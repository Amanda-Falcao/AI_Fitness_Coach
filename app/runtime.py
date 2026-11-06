"""Composition root for model, tools, and compiled agent graph."""

from app.agent.graph import create_agent_graph
from app.config.settings import Settings
from app.tools.calculation_tool import create_calculation_tool
from app.tools.rag_tool import create_rag_tool
from app.tools.web_search import create_web_search_tool


def build_agent_application(settings: Settings | None = None):
    """Build the runtime application after validating required integrations."""
    settings = settings or Settings.from_env(require_groq=True, require_tavily=True)
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is required to build the agent application")
    if not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required to build the agent application")
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise RuntimeError(
            "Groq/LangChain dependencies are missing; install the project requirements"
        ) from exc

    model = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model_name,
        temperature=0,
    )
    tools = [
        create_calculation_tool(),
        create_rag_tool(persist_directory=settings.chroma_persist_directory, k=3),
        create_web_search_tool(settings.tavily_api_key),
    ]
    return create_agent_graph(model, tools)
