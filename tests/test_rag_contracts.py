from types import SimpleNamespace

import pytest

from app.rag.ingestion import stable_chunk_ids
from app.rag.retriever import create_fitness_retriever


def test_chunk_ids_are_stable_and_change_when_content_or_source_changes():
    chunks = [SimpleNamespace(page_content="first"), SimpleNamespace(page_content="second")]

    ids = stable_chunk_ids("dados/knowledge.txt", chunks)

    assert ids == stable_chunk_ids("dados/knowledge.txt", chunks)
    assert len(set(ids)) == 2
    assert ids != stable_chunk_ids("other.txt", chunks)
    assert ids != stable_chunk_ids("dados/knowledge.txt", [chunks[0], SimpleNamespace(page_content="changed")])


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_retriever_rejects_invalid_k_before_loading_dependencies(k):
    with pytest.raises(ValueError, match="k must be a positive integer"):
        create_fitness_retriever(k=k)
