"""LangChain adapter for the internal fitness knowledge retriever."""

import hashlib
import json
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
        records = []
        for document in documents:
            source = document.metadata.get("source")
            if not isinstance(source, str) or not source.strip():
                raise RuntimeError("Retrieved knowledge chunk is missing source metadata")
            fingerprint = hashlib.sha256(
                f"{source.strip()}\0{document.page_content}".encode("utf-8")
            ).hexdigest()[:12]
            records.append(
                {
                    "ref_id": f"KB-{fingerprint}",
                    "source": source.strip(),
                    "evidence": document.page_content,
                }
            )
        return json.dumps(records, ensure_ascii=False)

    return fitness_knowledge_base_search
