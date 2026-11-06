"""Embedding model construction kept behind a lazy dependency boundary."""


def create_embedding_model(model_name: str = "all-MiniLM-L6-v2"):
    """Create the configured Hugging Face embedding model on demand."""
    if not model_name or not model_name.strip():
        raise ValueError("model_name must be a non-empty string")
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "Hugging Face embedding dependencies are missing; install the project requirements"
        ) from exc
    return HuggingFaceEmbeddings(model_name=model_name.strip())
