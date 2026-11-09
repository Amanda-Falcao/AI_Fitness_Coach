import sys
from types import SimpleNamespace

from app import runtime
from app.config.settings import Settings


def test_runtime_uses_low_reasoning_and_disables_automatic_retries(monkeypatch):
    captured = []

    class FakeChatGroq:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    monkeypatch.setitem(sys.modules, "langchain_groq", SimpleNamespace(ChatGroq=FakeChatGroq))
    monkeypatch.setattr(runtime, "create_rag_tool", lambda **kwargs: "rag")
    monkeypatch.setattr(runtime, "create_web_search_tool", lambda key: "web")
    monkeypatch.setattr(runtime, "create_agent_graph", lambda model, tools, **kwargs: (model, tools, kwargs))

    settings = Settings(groq_api_key="test-key", tavily_api_key="test-key")
    model, tools, graph_options = runtime.build_agent_application(settings)

    assert len(captured) == 2
    assert captured[0]["reasoning_effort"] == "low"
    assert captured[0]["model_kwargs"] == {"include_reasoning": False}
    assert captured[0]["max_retries"] == 0
    assert captured[1]["model_kwargs"] == {
        "include_reasoning": False,
        "max_completion_tokens": 4096,
    }
    assert graph_options["final_model"] is not None
    assert tools == ["rag"]


def test_web_search_is_only_added_when_explicitly_enabled(monkeypatch):
    class FakeChatGroq:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setitem(sys.modules, "langchain_groq", SimpleNamespace(ChatGroq=FakeChatGroq))
    monkeypatch.setattr(runtime, "create_rag_tool", lambda **kwargs: "rag")
    monkeypatch.setattr(runtime, "create_web_search_tool", lambda key: "web")
    monkeypatch.setattr(runtime, "create_agent_graph", lambda model, tools, **kwargs: tools)
    settings = Settings(groq_api_key="test-key", tavily_api_key="test-key")

    assert runtime.build_agent_application(settings, enable_web_search=True) == ["rag", "web"]
