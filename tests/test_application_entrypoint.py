from argparse import Namespace
from types import SimpleNamespace

import pytest

from app.agent.prompts import build_plan_prompt
from app.main import run_plan_generation, validate_profile


VALID_ARGS = Namespace(
    age=28,
    weight_kg=60.0,
    height_cm=164.0,
    gender="female",
    frequency=5,
    goal="hipertrofia",
)


def test_profile_validation_returns_only_expected_profile_fields():
    profile = validate_profile(VALID_ARGS)

    assert profile["frequency"] == 5
    assert profile["gender"] == "female"


def test_profile_validation_rejects_invalid_values():
    invalid_args = Namespace(**{**vars(VALID_ARGS), "height_cm": 0})

    with pytest.raises(ValueError, match="height_cm"):
        validate_profile(invalid_args)


def test_prompt_requests_three_weeks_and_expected_session_count():
    prompt = build_plan_prompt(
        {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 5, "goal": "hipertrofia"}
    )

    assert "exactly 15 sessions" in prompt
    assert "three weeks" in prompt


def test_run_plan_generation_saves_injected_graph_result(tmp_path):
    class FakeGraph:
        def invoke(self, state, config):
            assert state["messages"][0]["role"] == "user"
            assert config["recursion_limit"] == 12
            return {"messages": [SimpleNamespace(content="# Training plan\n")]}

    output = run_plan_generation(
        {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 5, "goal": "hipertrofia"},
        FakeGraph(),
        tmp_path / "plan.md",
    )

    assert output.read_text(encoding="utf-8") == "# Training plan\n"
