from types import SimpleNamespace

import pytest

from app.agent.nodes import create_agent_node, route_after_agent


def test_router_sends_tool_calls_to_tools_node():
    state = {"messages": [SimpleNamespace(tool_calls=[{"name": "lookup"}])]}

    assert route_after_agent(state) == "tools"


def test_router_finishes_when_model_has_no_tool_calls():
    state = {"messages": [SimpleNamespace(content="final answer")]}

    assert route_after_agent(state) == "end"


@pytest.mark.parametrize("state", [{}, {"messages": []}])
def test_router_rejects_empty_state(state):
    with pytest.raises(ValueError, match="at least one message"):
        route_after_agent(state)


def test_model_node_invokes_injected_model_and_returns_response():
    response = SimpleNamespace(content="done")

    class FakeModel:
        def invoke(self, messages):
            assert messages == ["user prompt"]
            return response

    node = create_agent_node(FakeModel())

    assert node({"messages": ["user prompt"]}) == {"messages": [response]}


def test_model_node_uses_final_model_after_internal_rag_result():
    tool_model = SimpleNamespace(invoke=lambda _: pytest.fail("tool model should not run"))
    final_response = SimpleNamespace(content='{"title":"Plan"}')
    bind_options = {}
    bound = SimpleNamespace(invoke=lambda messages: final_response)
    def bind_model(**kwargs):
        bind_options.update(kwargs)
        return bound

    final_model = SimpleNamespace(bind=bind_model)
    node = create_agent_node(tool_model, final_model=final_model)
    state = {"messages": [
        SimpleNamespace(type="tool", name="fitness_knowledge_base_search", content="[]")
    ], "sessions_per_week": 4}

    assert node(state) == {"messages": [final_response]}
    schema = bind_options["response_format"]["json_schema"]["schema"]
    assert "week_1_session_1" in schema["required"]
    assert "week_3_session_4" in schema["required"]
    assert "week_1_progression" not in schema["required"]


def test_model_node_rejects_empty_state():
    node = create_agent_node(SimpleNamespace(invoke=lambda _: None))

    with pytest.raises(ValueError, match="at least one message"):
        node({"messages": []})
