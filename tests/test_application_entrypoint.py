from argparse import Namespace
import json
from hashlib import sha256
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
EVIDENCE_TEXT = "Agachamento livre melhora força em quadríceps e glúteos."
EVIDENCE_REF = "KB-" + sha256(f"dados/conhecimento_fitness.txt\0{EVIDENCE_TEXT}".encode("utf-8")).hexdigest()[:12]


def valid_plan_content(sessions_per_week=5):
    return json.dumps({
        "title": "Plano de três semanas",
        "weeks": [
            {
                "week": week,
                "progression": f"Semana {week}: progrida apenas com execução correta.",
                "sessions": [
                    {
                        "day": day,
                        "title": f"Treino {day}",
                        "exercises": [{
                            "name": name,
                            "sets": 3,
                            "reps": "8-12",
                            "rest_seconds": 90,
                            "technique_cues": ["Mantenha a coluna neutra."],
                            "evidence_refs": [EVIDENCE_REF],
                        } for name in ("Agachamento livre", "Leg press", "Cadeira extensora")],
                    }
                    for day in range(1, sessions_per_week + 1)
                ],
            }
            for week in range(1, 4)
        ],
        "coach_analysis": "Aumente a carga gradualmente mantendo a técnica.",
        "safety": {
            "disclaimer": "Plano informativo.",
            "stop_conditions": ["Interrompa se sentir dor aguda."],
            "seek_professional_if": ["Procure profissional em caso de lesão."],
        },
    })


def test_profile_validation_returns_profile_with_local_reference_metrics():
    profile = validate_profile(VALID_ARGS)

    assert profile["frequency"] == 5
    assert profile["gender"] == "female"
    assert "BMI:" in profile["reference_metrics"]


def test_profile_validation_rejects_invalid_values():
    invalid_args = Namespace(**{**vars(VALID_ARGS), "height_cm": 0})

    with pytest.raises(ValueError, match="height_cm"):
        validate_profile(invalid_args)


@pytest.mark.parametrize("frequency", [0, 8, True, 2.5])
def test_profile_validation_requires_one_to_seven_complete_weekly_sessions(frequency):
    invalid_args = Namespace(**{**vars(VALID_ARGS), "frequency": frequency})

    with pytest.raises(ValueError, match="frequency"):
        validate_profile(invalid_args)


def test_prompt_requests_three_weeks_and_expected_session_count():
    prompt = build_plan_prompt(
        {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 5, "goal": "hipertrofia"}
    )

    assert "exactly 5 sessions per week (15 total)" in prompt
    assert "3 weeks" in prompt
    assert "Include coach_analysis and safety with all required fields" in prompt
    assert "valid JSON object" in prompt
    assert "week_1_session_1 through week_3_session_5" in prompt
    assert "exercise_1, exercise_2, exercise_3" in prompt
    assert "exactly 3 exercises" in prompt


def test_four_day_prompt_requires_upper_lower_ab_and_conditional_progression():
    prompt = build_plan_prompt(
        {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 4, "goal": "hipertrofia"}
    )

    assert "Upper A, Lower A, Upper B, Lower B" in prompt
    assert "week_1_progression" in prompt
    assert "only when every set was completed with sound technique" in prompt
    assert "Do not attach generic evidence to a specific exercise claim" in prompt


def test_run_plan_generation_saves_injected_graph_result(tmp_path):
    class FakeGraph:
        def invoke(self, state, config):
            assert state["messages"][0]["role"] == "user"
            assert config["recursion_limit"] == 4
            rag_result = json.dumps([{
                "ref_id": EVIDENCE_REF,
                "source": "dados/conhecimento_fitness.txt",
                "evidence": EVIDENCE_TEXT,
            }], ensure_ascii=False)
            return {"messages": [
                SimpleNamespace(name="fitness_knowledge_base_search", content=rag_result),
                SimpleNamespace(content=valid_plan_content()),
            ]}

    output = run_plan_generation(
        {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 5, "goal": "hipertrofia"},
        FakeGraph(),
        tmp_path / "plan.md",
    )

    assert output.read_text(encoding="utf-8").startswith("# Plano de três semanas\n")
    assert output.read_text(encoding="utf-8").count("### Sessão") == 15
    assert EVIDENCE_REF in output.read_text(encoding="utf-8")
    assert "dados/conhecimento_fitness.txt" in output.read_text(encoding="utf-8")


def test_run_plan_generation_does_not_write_invalid_output(tmp_path):
    class InvalidGraph:
        def invoke(self, state, config):
            return {"messages": [SimpleNamespace(content='{"weeks": []}') ]}

    destination = tmp_path / "invalid.md"
    with pytest.raises(RuntimeError, match="output contract"):
        run_plan_generation(
            {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 5, "goal": "hipertrofia"},
            InvalidGraph(),
            destination,
        )
    assert not destination.exists()


def test_rate_limit_failure_tells_user_to_wait_without_retrying(tmp_path):
    class RateLimitError(Exception):
        pass

    class LimitedGraph:
        def invoke(self, state, config):
            raise RateLimitError("HTTP 429")

    with pytest.raises(RuntimeError, match="free-tier limit window"):
        run_plan_generation(
            {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 5, "goal": "hipertrofia"},
            LimitedGraph(),
            tmp_path / "limited.md",
        )
