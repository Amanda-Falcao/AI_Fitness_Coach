"""Tavily web-search tool factory with explicit configuration and failures."""


def create_web_search_tool(api_key: str):
    """Create a Tavily-backed LangChain tool without initializing clients at import."""
    if not api_key or not api_key.strip():
        raise ValueError("Tavily API key is required to create the web search tool")
    try:
        from langchain_core.tools import tool
        from tavily import TavilyClient
    except ImportError as exc:
        raise RuntimeError(
            "Tavily/LangChain dependencies are missing; install the project requirements"
        ) from exc

    client = TavilyClient(api_key=api_key.strip())

    @tool
    def web_search(query: str) -> str:
        """Search the web for current, general fitness training information."""
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        try:
            response = client.search(query=query.strip(), search_depth="basic", max_results=3)
        except Exception as exc:
            raise RuntimeError("Tavily web search failed") from exc
        results = response.get("results", [])
        if not results:
            return "The search completed but returned no relevant results."
        return "\n\n".join(
            f"{item.get('title', 'Search result')}: {item.get('content', '')}"
            for item in results[:3]
        )

    return web_search
