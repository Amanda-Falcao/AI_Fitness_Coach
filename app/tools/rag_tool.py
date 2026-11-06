"""LangChain adapter for the internal fitness knowledge retriever."""

from pathlib import Path

from app.rag.retriever import create_fitness_retriever


def create_rag_tool(*, persist_directory: str | Path | None = None, k: int = 3):
    """Create a retriever tool after validating the persisted knowledge base."""
    try:
        from langchain_core.tools import tool
    except ImportError as exc:
        raise RuntimeError(
            "LangChain tool dependencies are missing; install the project requirements"
        ) from exc

    retriever = create_fitness_retriever(
        persist_directory=persist_directory,
        k=k,
    )
    @tool
    def fitness_knowledge_base_search(query: str) -> str:
        """Search the internal fitness knowledge base for exercise and technique guidance."""
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        documents = retriever.invoke(query.strip())
        if not documents:
            return "No relevant knowledge documents were found."
        return "\n\n".join(
            f"Source: {document.metadata.get('source', 'unknown')}\n{document.page_content}"
            for document in documents
        )

    return fitness_knowledge_base_search
