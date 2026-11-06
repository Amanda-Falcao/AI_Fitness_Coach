"""Validated access to the persisted Chroma knowledge collection."""

from pathlib import Path

from app.config.settings import Settings
from app.rag.embeddings import create_embedding_model
from app.rag.ingestion import resolve_project_path


class KnowledgeBaseError(RuntimeError):
    """Raised when the persisted knowledge base is unavailable or empty."""


def create_fitness_retriever(
    *,
    persist_directory: str | Path | None = None,
    embedding_model_name: str | None = None,
    embedding_model=None,
    vector_store_class=None,
    k: int = 3,
):
    """Open the existing Chroma collection and return a top-k retriever."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    settings = Settings.from_env()
    path = resolve_project_path(persist_directory or settings.chroma_persist_directory)
    if not path.is_dir():
        raise KnowledgeBaseError(
            f"Chroma directory does not exist: {path}. Run `python -m app.rag.ingestion` first."
        )
    if embedding_model is None:
        embedding_model = create_embedding_model(embedding_model_name or settings.embedding_model_name)
    if vector_store_class is None:
        try:
            from langchain_chroma import Chroma
        except ImportError as exc:
            raise RuntimeError(
                "Chroma dependencies are missing; install the project requirements"
            ) from exc
        vector_store_class = Chroma

    try:
        vector_store = vector_store_class(
            persist_directory=str(path), embedding_function=embedding_model
        )
        stored_ids = vector_store.get(limit=1).get("ids", [])
    except Exception as exc:
        raise KnowledgeBaseError(f"Could not open Chroma collection at {path}: {exc}") from exc
    if not stored_ids:
        raise KnowledgeBaseError(f"Chroma collection is empty at {path}.")
    return vector_store.as_retriever(search_kwargs={"k": k})
