import json
from types import SimpleNamespace

import pytest

from app.rag.citations import citation_registry_from_messages


def test_extracts_only_internal_rag_citation_records():
    content = json.dumps([
        {"ref_id": "KB-aaaaaaaaaaaa", "source": "guide.txt", "evidence": "Supported cue."}
    ])
    messages = [
        SimpleNamespace(name="fitness_knowledge_base_search", content=content),
        SimpleNamespace(name="web_search", content=content),
        SimpleNamespace(name=None, content=content),
    ]

    assert citation_registry_from_messages(messages) == {
        "KB-aaaaaaaaaaaa": {"source": "guide.txt", "evidence": "Supported cue."}
    }


@pytest.mark.parametrize(
    "content",
    [
        "[{broken]",
        "{}",
        '[{"ref_id":"invented","source":"guide.txt","evidence":"text"}]',
    ],
)
def test_rejects_malformed_or_invalid_rag_citations(content):
    messages = [SimpleNamespace(name="fitness_knowledge_base_search", content=content)]

    with pytest.raises(ValueError, match="RAG tool"):
        citation_registry_from_messages(messages)


def test_rejects_conflicting_records_for_same_reference():
    first = {"ref_id": "KB-aaaaaaaaaaaa", "source": "guide.txt", "evidence": "first"}
    second = {"ref_id": "KB-aaaaaaaaaaaa", "source": "guide.txt", "evidence": "second"}
    messages = [
        SimpleNamespace(name="fitness_knowledge_base_search", content=json.dumps([first, second]))
    ]

    with pytest.raises(ValueError, match="Conflicting"):
        citation_registry_from_messages(messages)
