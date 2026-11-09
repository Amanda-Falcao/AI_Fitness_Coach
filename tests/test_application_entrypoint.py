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
EXERCISE_EVIDENCE = {
    "Supino Reto (Barra)": "### Supino Reto (Barra)\nRegião: Superior.\nMúsculos: Peitoral maior, tríceps e deltoide anterior.\nDicas: Mantenha as escápulas estáveis no banco.",
    "Remada Curvada (Barra)": "### Remada Curvada (Barra)\nRegião: Superior.\nMúsculos: Dorsais, bíceps e trapézio.\nDicas: Puxe a barra em direção ao abdômen.",
    "Desenvolvimento Militar (Overhead Press)": "### Desenvolvimento Militar (Overhead Press)\nRegião: Superior.\nMúsculos: Deltoides e tríceps.\nDicas: Contraia o abdômen e os glúteos.",
    "Flexão de Braços (Push-up)": "### Flexão de Braços (Push-up)\nRegião: Superior.\nMúsculos: Peitoral, tríceps e ombros.\nDicas: Mantenha o tronco alinhado.",
    "Agachamento Livre (Barra)": "### Agachamento Livre (Barra)\nRegião: Inferior.\nMúsculos: Quadríceps e glúteos.\nDicas: Mantenha a coluna neutra.",
    "Levantamento Terra (Deadlift)": "### Levantamento Terra (Deadlift)\nRegião: Inferior.\nMúsculos: Glúteos e posteriores.\nDicas: Mantenha a barra próxima ao corpo.",
    "Levantamento Terra Romeno": "### Levantamento Terra Romeno\nRegião: Inferior.\nMúsculos: Posteriores e glúteos.\nDicas: Leve o quadril para trás.",
    "Avanço Reverso (Reverse Lunge)": "### Avanço Reverso (Reverse Lunge)\nRegião: Inferior.\nMúsculos: Glúteos e coxas.\nDicas: Dê um passo para trás com controle.",
}
EVIDENCE_REFS = {
    name: "KB-" + sha256(f"dados/conhecimento_fitness.txt\0{text}".encode("utf-8")).hexdigest()[:12]
    for name, text in EXERCISE_EVIDENCE.items()
}
RULE_EVIDENCE = "Hipertrofia\nSéries/Repetições: 3 a 4 séries, 8 a 12 repetições.\nDescanso: 60 a 90 segundos."
RULE_REF = "KB-" + sha256(f"dados/conhecimento_fitness.txt\0{RULE_EVIDENCE}".encode("utf-8")).hexdigest()[:12]


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
                            "evidence_refs": [EVIDENCE_REFS[name]],
                        } for name in list(EXERCISE_EVIDENCE)[4:7]],
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
    assert "progression rules deterministically" in prompt
    assert "Keep session days, titles, exercise names, sets, reps, and rest identical across all weeks" in prompt
    assert "Do not attach generic evidence to a specific exercise" in prompt


def test_run_plan_generation_saves_injected_graph_result(tmp_path):
    class FakeGraph:
        def invoke(self, state, config):
            assert state["messages"][0]["role"] == "user"
            assert config["recursion_limit"] == 4
            rag_result = json.dumps([{
                "ref_id": EVIDENCE_REFS[name],
                "source": "dados/conhecimento_fitness.txt",
                "evidence": text,
            } for name, text in EXERCISE_EVIDENCE.items()] + [{
                "ref_id": RULE_REF,
                "source": "dados/conhecimento_fitness.txt",
                "evidence": RULE_EVIDENCE,
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
    assert EVIDENCE_REFS["Agachamento Livre (Barra)"] in output.read_text(encoding="utf-8")
    assert "dados/conhecimento_fitness.txt" in output.read_text(encoding="utf-8")


def test_four_day_generation_renders_complete_document_from_retrieved_sections(tmp_path):
    class FakeGraph:
        def invoke(self, state, config):
            records = [{
                "ref_id": EVIDENCE_REFS[name], "source": "dados/conhecimento_fitness.txt", "evidence": text,
            } for name, text in EXERCISE_EVIDENCE.items()]
            records.append({"ref_id": RULE_REF, "source": "dados/conhecimento_fitness.txt", "evidence": RULE_EVIDENCE})
            weeks = []
            layouts = (
                ("Upper A", ("Supino Reto (Barra)", "Remada Curvada (Barra)", "Desenvolvimento Militar (Overhead Press)")),
                ("Lower A", ("Agachamento Livre (Barra)", "Levantamento Terra (Deadlift)", "Avanço Reverso (Reverse Lunge)")),
                ("Upper B", ("Flexão de Braços (Push-up)", "Remada Curvada (Barra)", "Desenvolvimento Militar (Overhead Press)")),
                ("Lower B", ("Agachamento Livre (Barra)", "Levantamento Terra Romeno", "Avanço Reverso (Reverse Lunge)")),
            )
            for week in range(1, 4):
                weeks.append({"week": week, "progression": "model progression", "sessions": [
                    {"day": index, "title": title, "exercises": [{
                        "name": name, "sets": 3, "reps": "8-12", "rest_seconds": 90,
                        "technique_cues": ["untrusted model cue"], "evidence_refs": [EVIDENCE_REFS[name]],
                    } for name in names]} for index, (title, names) in enumerate(layouts, 1)
                ]})
            response = json.dumps({
                "title": "Plano Upper/Lower de quatro dias", "weeks": weeks,
                "coach_analysis": "Progrida de forma condicionada à execução.",
                "safety": {"disclaimer": "Plano informativo.", "stop_conditions": ["Pare em caso de dor."],
                           "seek_professional_if": ["Procure orientação em caso de lesão."]},
            }, ensure_ascii=False)
            return {"messages": [
                SimpleNamespace(name="fitness_knowledge_base_search", content=json.dumps(records, ensure_ascii=False)),
                SimpleNamespace(content=response),
            ]}

    output = run_plan_generation(
        {"age": 28, "weight_kg": 60, "height_cm": 164, "gender": "female", "frequency": 4, "goal": "hipertrofia"},
        FakeGraph(), tmp_path / "four_day_plan.md",
    )
    markdown = output.read_text(encoding="utf-8")
    assert markdown.count("### Sessão") == 12
    assert markdown.count("| Exercício | Séries | Repetições | Descanso | Referência |") == 12
    assert "## Guia de execução" in markdown
    assert markdown.count("Mantenha a coluna neutra.") == 1
    assert "untrusted model cue" not in markdown
    assert "Hipertrofia\nSéries/Repetições" not in markdown


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
