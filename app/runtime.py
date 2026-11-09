"""Composition root for model, tools, and compiled agent graph."""

from app.agent.graph import create_agent_graph
from app.config.settings import Settings
from app.tools.rag_tool import create_rag_tool
from app.tools.web_search import create_web_search_tool


def build_agent_application(settings: Settings | None = None, *, enable_web_search: bool = False):
    """Build the runtime application after validating required integrations."""
    settings = settings or Settings.from_env(require_groq=True, require_tavily=enable_web_search)
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is required to build the agent application")
    if enable_web_search and not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required to build the agent application")
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise RuntimeError(
            "Groq/LangChain dependencies are missing; install the project requirements"
        ) from exc

    model_options = dict(
        api_key=settings.groq_api_key,
        model=settings.groq_model_name,
        temperature=0,
        reasoning_effort="low",
        model_kwargs={"include_reasoning": False},
        max_retries=0,
    )
    model = ChatGroq(**model_options)
    final_model_options = dict(model_options)
    # Groq's default completion budget is 1024 tokens, too small for a three-week plan.
    final_model_options["model_kwargs"] = {
        "include_reasoning": False,
        "max_completion_tokens": 4096,
    }
    final_model = ChatGroq(**final_model_options)
    # The single local retrieval must expose every exercise section so the
    # final plan can be validated without another model or search call.
    tools = [create_rag_tool(persist_directory=settings.chroma_persist_directory, k=32)]
    if enable_web_search:
        tools.append(create_web_search_tool(settings.tavily_api_key or ""))
    return create_agent_graph(model, tools, final_model=final_model)
