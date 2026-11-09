import json

import pytest

from app.agent.plan_output import (
    PlanValidationError,
    parse_and_validate_plan,
    render_plan_markdown,
)


def valid_plan(sessions_per_week=2):
    return {
        "title": "Plano de três semanas",
        "weeks": [
            {
                "week": week_number,
                "sessions": [
                    {
                        "day": day,
                        "title": f"Treino {day}",
                        "exercises": [
                            {
                                "name": "Agachamento livre",
                                "sets": 3,
                                "reps": "8-12",
                                "rest_seconds": 90,
                                "technique_cues": ["Mantenha a coluna neutra."],
                                "evidence_refs": ["KB-aaaaaaaaaaaa"],
                            }
                        ],
                    }
                    for day in range(1, sessions_per_week + 1)
                ],
            }
            for week_number in range(1, 4)
        ],
        "coach_analysis": "Aumente a carga gradualmente mantendo a técnica.",
        "safety": {
            "disclaimer": "Este plano é informativo e não substitui avaliação individual.",
            "stop_conditions": ["Interrompa se sentir dor aguda ou tontura."],
            "seek_professional_if": ["Procure profissional em caso de lesão ou condição de saúde."],
        },
    }


VALID_CITATIONS = {
    "KB-aaaaaaaaaaaa": {
        "source": "guide.txt",
        "evidence": "Agachamento: mantenha a coluna neutra.",
    }
}


def test_validates_exact_weekly_session_count_and_renders_markdown():
    plan = parse_and_validate_plan(
        json.dumps(valid_plan()), sessions_per_week=2, citation_registry=VALID_CITATIONS
    )

    markdown = render_plan_markdown(plan, VALID_CITATIONS)
    assert markdown.startswith("# Plano de três semanas")
    assert markdown.count("### Sessão") == 6
    assert "## Segurança" in markdown
    assert "Procure profissional" in markdown
    assert "guide.txt" in markdown
    assert "[KB-aaaaaaaaaaaa]" in markdown


def test_rejects_invalid_json_and_markdown_fences():
    for response in ("not json", "```json\n{}\n```"):
        with pytest.raises(PlanValidationError, match="valid JSON"):
            parse_and_validate_plan(response, sessions_per_week=2)


def test_rejects_incomplete_weeks_and_wrong_session_count():
    plan = valid_plan()
    plan["weeks"][1]["sessions"].pop()

    with pytest.raises(PlanValidationError, match="exactly 2 sessions"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_rejects_unsafe_or_invalid_exercise_parameters():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["sets"] = 0

    with pytest.raises(PlanValidationError, match="sets must be an integer"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_rejects_missing_safety_guidance():
    plan = valid_plan()
    plan["safety"]["stop_conditions"] = []

    with pytest.raises(PlanValidationError, match="stop_conditions"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_rejects_duplicate_days_in_a_week():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][1]["day"] = 1

    with pytest.raises(PlanValidationError, match="repeats a training day"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_rejects_unexpected_fields_and_boolean_week_numbers():
    plan = valid_plan()
    plan["weeks"][0]["week"] = True

    with pytest.raises(PlanValidationError, match="integer between"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["unexpected"] = "field"
    with pytest.raises(PlanValidationError, match="unexpected: unexpected"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_rejects_reference_not_returned_by_rag_tool():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["evidence_refs"] = ["KB-bbbbbbbbbbbb"]

    with pytest.raises(PlanValidationError, match="not returned by the RAG tool"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)
