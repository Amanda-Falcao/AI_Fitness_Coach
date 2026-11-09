from types import SimpleNamespace

import pytest

from app.rag.ingestion import stable_chunk_ids
from app.rag.retriever import create_fitness_retriever
from app.rag.ingestion import IngestionError, ingest_knowledge_base
from app.rag.retriever import KnowledgeBaseError
from app.rag.evaluation import evaluate_retrieval


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


def test_ingestion_upserts_deterministic_ids_and_deletes_stale_source_chunks(monkeypatch, tmp_path):
    import app.rag.ingestion as ingestion

    source_path = tmp_path / "knowledge.txt"
    source_path.write_text("updated source", encoding="utf-8")
    chunks = [SimpleNamespace(page_content="new chunk", metadata={"source": "knowledge.txt"})]
    monkeypatch.setattr(ingestion, "load_and_split_documents", lambda *args, **kwargs: ("knowledge.txt", chunks))
    stable_id = ingestion.stable_chunk_ids("knowledge.txt", chunks)[0]

    class FakeVectorStore:
        instance = None

        def __init__(self, **kwargs):
            self.added = None
            self.deleted = None
            self.ids = None
            type(self).instance = self

        def get(self, where):
            assert where == {"source": "knowledge.txt"}
            return {"ids": self.ids if self.ids is not None else ["stale-id", stable_id]}

        def add_documents(self, documents, ids):
            self.added = (documents, ids)
            self.ids = list(set(self.ids or ["stale-id", stable_id]) | set(ids))

        def delete(self, ids):
            self.deleted = ids
            self.ids = [item for item in self.ids if item not in ids]

    store = FakeVectorStore
    result = ingest_knowledge_base(
        source_path,
        persist_directory=tmp_path / "chroma",
        embedding_model=object(),
        vector_store_class=store,
    )
    assert result.chunk_count == 1
    assert store.instance.added == (chunks, list(result.chunk_ids))
    assert store.instance.deleted == ["stale-id"]


def test_ingestion_keeps_old_ids_when_upsert_fails(monkeypatch, tmp_path):
    import app.rag.ingestion as ingestion

    source_path = tmp_path / "knowledge.txt"
    source_path.write_text("updated source", encoding="utf-8")
    chunks = [SimpleNamespace(page_content="new chunk", metadata={"source": "knowledge.txt"})]
    monkeypatch.setattr(ingestion, "load_and_split_documents", lambda *args, **kwargs: ("knowledge.txt", chunks))

    class FailingVectorStore:
        instance = None

        def __init__(self, **kwargs):
            self.deleted = False
            type(self).instance = self

        def get(self, where):
            return {"ids": ["old-id"]}

        def add_documents(self, documents, ids):
            raise OSError("storage failure")

        def delete(self, ids):
            self.deleted = True

    store = FailingVectorStore
    with pytest.raises(IngestionError, match="Could not update Chroma"):
        ingest_knowledge_base(
            source_path,
            persist_directory=tmp_path / "chroma",
            embedding_model=object(),
            vector_store_class=store,
        )
    assert not store.instance.deleted


def test_retriever_rejects_missing_or_empty_store_before_query(tmp_path):
    class EmptyVectorStore:
        def __init__(self, **kwargs):
            pass

        def get(self, limit):
            return {"ids": []}

    with pytest.raises(KnowledgeBaseError, match="does not exist"):
        create_fitness_retriever(
            persist_directory=tmp_path / "missing",
            embedding_model=object(),
            vector_store_class=EmptyVectorStore,
        )

    empty_path = tmp_path / "empty"
    empty_path.mkdir()
    with pytest.raises(KnowledgeBaseError, match="empty"):
        create_fitness_retriever(
            persist_directory=empty_path,
            embedding_model=object(),
            vector_store_class=EmptyVectorStore,
        )


def test_retrieval_evaluation_reports_hit_rate_mrr_and_latency():
    cases = [
        {"query": "progression", "expected_evidence": "progressive overload"},
        {"query": "rest", "expected_evidence": "three minutes"},
    ]

    def fake_retrieve(query):
        if query == "progression":
            return [SimpleNamespace(page_content="Progressive overload")]
        return [
            SimpleNamespace(page_content="unrelated"),
            SimpleNamespace(page_content="Rest for three minutes"),
        ]

    metrics = evaluate_retrieval(cases, fake_retrieve, k=2)

    assert metrics["hit_rate_at_2"] == 1.0
    assert metrics["mrr"] == 0.75
    assert metrics["query_count"] == 2
    assert metrics["mean_latency_ms"] >= 0


@pytest.mark.parametrize("cases", [[], [{"query": "", "expected_evidence": "x"}]])
def test_retrieval_evaluation_validates_cases(cases):
    with pytest.raises(ValueError):
        evaluate_retrieval(cases, lambda query: [])
