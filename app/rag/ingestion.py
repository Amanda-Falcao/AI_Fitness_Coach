"""Document loading, chunking, and idempotent Chroma ingestion."""

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from app.config.settings import Settings
from app.rag.embeddings import create_embedding_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_FILE = PROJECT_ROOT / "dados" / "conhecimento_fitness.txt"


class IngestionError(RuntimeError):
    """Raised when the knowledge source cannot be prepared or stored."""


@dataclass(frozen=True)
class IngestionResult:
    source: str
    chunk_count: int
    chunk_ids: tuple[str, ...]


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from the repository root, independent of cwd."""
    candidate = Path(path).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()


def stable_chunk_ids(source: str, documents: list) -> list[str]:
    """Build reproducible IDs from source, chunk order, and chunk text."""
    ids = []
    for index, document in enumerate(documents):
        identity = f"{source}\0{index}\0{document.page_content}"
        ids.append(hashlib.sha256(identity.encode("utf-8")).hexdigest())
    return ids


def load_and_split_documents(
    knowledge_file: str | Path = DEFAULT_KNOWLEDGE_FILE,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):
    """Load UTF-8 text and split it using the prototype's current parameters."""
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    if isinstance(chunk_overlap, bool) or not isinstance(chunk_overlap, int) or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must be an integer from 0 up to chunk_size - 1")

    source_path = resolve_project_path(knowledge_file)
    if not source_path.is_file():
        raise IngestionError(f"Knowledge source does not exist: {source_path}")
    try:
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError(
            "Document processing dependencies are missing; install the project requirements"
        ) from exc

    try:
        content = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IngestionError(f"Could not read knowledge source {source_path}: {exc}") from exc
    if not content.strip():
        raise IngestionError(f"Knowledge source is empty: {source_path}")

    try:
        source = source_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        source = source_path.as_posix()
    # Exercise sections are kept intact so retrieval and citations cannot mix
    # the technique cue for one movement with another movement's description.
    section_pattern = re.compile(r"(?m)^### (.+?)\s*$")
    matches = list(section_pattern.finditer(content))
    chunks = []
    if matches:
        general_content = content[:matches[0].start()].strip()
        if general_content:
            general_document = Document(page_content=general_content, metadata={"source": source})
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                is_separator_regex=False,
            )
            chunks.extend(splitter.split_documents([general_document]))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            section = content[match.start():end].strip()
            title = match.group(1).strip()
            chunks.append(Document(
                page_content=section,
                metadata={"source": source, "section": title},
            ))
    else:
        document = Document(page_content=content, metadata={"source": source})
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        chunks = splitter.split_documents([document])
    if not chunks:
        raise IngestionError(f"No chunks were produced from knowledge source: {source}")
    return source, chunks


def ingest_knowledge_base(
    knowledge_file: str | Path = DEFAULT_KNOWLEDGE_FILE,
    *,
    persist_directory: str | Path = "dados/chroma_db",
    embedding_model_name: str = "all-MiniLM-L6-v2",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    embedding_model=None,
    vector_store_class=None,
) -> IngestionResult:
    """Upsert chunks and remove stale chunks for this source after successful upsert."""
    source, chunks = load_and_split_documents(
        knowledge_file, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunk_ids = stable_chunk_ids(source, chunks)
    if embedding_model is None:
        embedding_model = create_embedding_model(embedding_model_name)
    if vector_store_class is None:
        try:
            from langchain_chroma import Chroma
        except ImportError as exc:
            raise RuntimeError(
                "Chroma dependencies are missing; install the project requirements"
            ) from exc
        vector_store_class = Chroma

    store_path = resolve_project_path(persist_directory)
    store_path.mkdir(parents=True, exist_ok=True)
    vector_store = vector_store_class(
        persist_directory=str(store_path), embedding_function=embedding_model
    )
    try:
        existing = vector_store.get(where={"source": source})
        old_ids = set(existing.get("ids", []))
        vector_store.add_documents(documents=chunks, ids=chunk_ids)
        stale_ids = old_ids.difference(chunk_ids)
        if stale_ids:
            vector_store.delete(ids=sorted(stale_ids))
        stored_ids = set(vector_store.get(where={"source": source}).get("ids", []))
        if stored_ids != set(chunk_ids):
            raise IngestionError(
                f"Chroma verification failed for {source}: expected {len(chunk_ids)} chunks, found {len(stored_ids)}"
            )
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Could not update Chroma collection for {source}: {exc}") from exc

    return IngestionResult(source, len(chunks), tuple(chunk_ids))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the fitness knowledge text into Chroma.")
    parser.add_argument("--source", default=str(DEFAULT_KNOWLEDGE_FILE))
    args = parser.parse_args()
    settings = Settings.from_env()
    result = ingest_knowledge_base(
        args.source,
        persist_directory=settings.chroma_persist_directory,
        embedding_model_name=settings.embedding_model_name,
    )
    print(f"Ingested {result.chunk_count} chunks from {result.source} into Chroma.")


if __name__ == "__main__":
    main()
