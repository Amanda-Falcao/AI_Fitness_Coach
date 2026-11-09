import json
import re
import sys
from types import ModuleType, SimpleNamespace

import pytest


def install_fake_langchain_tool(monkeypatch):
    core = ModuleType("langchain_core")
    tools = ModuleType("langchain_core.tools")
    tools.tool = lambda function: function
    core.tools = tools
    monkeypatch.setitem(sys.modules, "langchain_core", core)
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools)


def test_calculation_tool_delegates_to_validated_shared_function(monkeypatch):
    install_fake_langchain_tool(monkeypatch)
    from app.tools.calculation_tool import create_calculation_tool

    tool = create_calculation_tool()
    result = tool(
        age_years=30,
        weight_kg=70,
        height_cm=175,
        sex="male",
        training_days_per_week=3,
        goal="maintenance",
    )

    assert "BMI" in result
    assert "estimate" in result.lower()
    with pytest.raises(ValueError):
        tool(
            age_years=0,
            weight_kg=70,
            height_cm=175,
            sex="male",
            training_days_per_week=3,
            goal="maintenance",
        )


def test_rag_tool_returns_source_and_rejects_blank_queries(monkeypatch):
    install_fake_langchain_tool(monkeypatch)
    from app.tools import rag_tool

    class FakeRetriever:
        def invoke(self, query):
            assert query == "squat technique"
            return [SimpleNamespace(metadata={"source": "guide.txt"}, page_content="Keep a neutral spine.")]

    monkeypatch.setattr(rag_tool, "create_fitness_retriever", lambda **kwargs: FakeRetriever())
    tool = rag_tool.create_rag_tool()

    records = json.loads(tool("  squat technique  "))
    assert records[0]["source"] == "guide.txt"
    assert records[0]["evidence"] == "Keep a neutral spine."
    assert re.fullmatch(r"KB-[0-9a-f]{12}", records[0]["ref_id"])
    with pytest.raises(ValueError, match="non-empty"):
        tool("  ")


def test_rag_tool_reports_no_matching_documents(monkeypatch):
    install_fake_langchain_tool(monkeypatch)
    from app.tools import rag_tool

    class EmptyRetriever:
        def invoke(self, query):
            return []

    monkeypatch.setattr(rag_tool, "create_fitness_retriever", lambda **kwargs: EmptyRetriever())
    assert rag_tool.create_rag_tool()("unknown topic") == "No relevant knowledge documents were found."


def test_rag_tool_rejects_documents_without_source_metadata(monkeypatch):
    install_fake_langchain_tool(monkeypatch)
    from app.tools import rag_tool

    class MissingSourceRetriever:
        def invoke(self, query):
            return [SimpleNamespace(metadata={}, page_content="An uncited passage.")]

    monkeypatch.setattr(rag_tool, "create_fitness_retriever", lambda **kwargs: MissingSourceRetriever())
    with pytest.raises(RuntimeError, match="missing source metadata"):
        rag_tool.create_rag_tool()("exercise")


def test_tavily_tool_uses_client_and_surfaces_safe_error(monkeypatch):
    install_fake_langchain_tool(monkeypatch)
    tavily = ModuleType("tavily")

    class FakeTavilyClient:
        def __init__(self, api_key):
            assert api_key == "test-key"

        def search(self, **kwargs):
            assert kwargs["query"] == "training"
            return {"results": [{"title": "Guide", "content": "Progress gradually."}]}

    tavily.TavilyClient = FakeTavilyClient
    monkeypatch.setitem(sys.modules, "tavily", tavily)
    from app.tools.web_search import create_web_search_tool

    tool = create_web_search_tool(" test-key ")
    assert tool(" training ") == "Guide: Progress gradually."
    with pytest.raises(ValueError, match="non-empty"):
        tool(" ")


def test_tavily_tool_wraps_upstream_error_without_leaking_details(monkeypatch):
    install_fake_langchain_tool(monkeypatch)
    tavily = ModuleType("tavily")

    class FailingClient:
        def __init__(self, api_key):
            pass

        def search(self, **kwargs):
            raise RuntimeError("sensitive upstream detail")

    tavily.TavilyClient = FailingClient
    monkeypatch.setitem(sys.modules, "tavily", tavily)
    from app.tools.web_search import create_web_search_tool

    with pytest.raises(RuntimeError, match="Tavily web search failed") as error:
        create_web_search_tool("test-key")("training")
    assert "sensitive upstream detail" not in str(error.value)
