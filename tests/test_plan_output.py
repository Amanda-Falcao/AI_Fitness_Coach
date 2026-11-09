import json

import pytest

from app.agent.plan_output import (
    PlanValidationError,
    groq_plan_response_format,
    normalize_groq_plan,
    parse_and_validate_plan,
    render_plan_markdown,
)


def test_groq_response_schema_requires_all_contract_fields_and_closes_objects():
    response_format = groq_plan_response_format(4)
    schema = response_format["json_schema"]["schema"]

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert schema["required"][0] == "title"
    assert schema["required"][-2:] == ["coach_analysis", "safety"]
    assert all(f"week_{week}_progression" in schema["required"] for week in range(1, 4))
    assert schema["additionalProperties"] is False
    assert "week_1_session_1" in schema["required"]
    assert "week_3_session_4" in schema["required"]
    assert len([key for key in schema["required"] if key.startswith("week_")]) == 15
    assert schema["properties"]["safety"]["required"] == [
        "disclaimer", "stop_conditions", "seek_professional_if"
    ]


def test_normalize_groq_plan_converts_numbered_slots_to_application_lists():
    plan = {
        "title": "Plan",
        "coach_analysis": "Progress gradually.",
        **{f"week_{week}_progression": f"Week {week}: progress conditionally." for week in range(1, 4)},
        "safety": {
            "disclaimer": "General guidance.",
            "stop_conditions": ["Stop if you feel pain."],
            "seek_professional_if": ["Ask a professional if unsure."],
        },
    }
    for week_number in range(1, 4):
        plan[f"week_{week_number}_session_1"] = {
            "day": 1,
            "title": "Full body",
            **{
                f"exercise_{exercise_number}": {
                    "name": f"Exercise {exercise_number}",
                    "sets": 3,
                    "reps": "8-12",
                    "rest_seconds": 90,
                    "technique_cue": "Use controlled movement",
                    "evidence_ref": "KB-000000000000",
                }
                for exercise_number in range(1, 4)
            },
        }
    normalized = json.loads(normalize_groq_plan(json.dumps(plan), 1))

    assert len(normalized["weeks"]) == 3
    assert len(normalized["weeks"][0]["sessions"]) == 1
    assert len(normalized["weeks"][0]["sessions"][0]["exercises"]) == 3
    assert normalized["weeks"][0]["sessions"][0]["exercises"][0]["technique_cues"] == [
        "Use controlled movement"
    ]


def valid_plan(sessions_per_week=2):
    return {
        "title": "Plano de três semanas",
        "weeks": [
            {
                "week": week_number,
                "progression": f"Semana {week_number}: progrida se mantiver a técnica.",
                "sessions": [
                    {
                        "day": day,
                        "title": f"Treino {day}",
                        "exercises": [
                            {
                                "name": exercise_name,
                                "sets": 3,
                                "reps": "8-12",
                                "rest_seconds": 90,
                                "technique_cues": ["Mantenha a coluna neutra."],
                                "evidence_refs": ["KB-aaaaaaaaaaaa"],
                            }
                            for exercise_name in ("Agachamento livre", "Leg press", "Cadeira extensora")
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
    assert "**Progressão:** Semana 1" in markdown
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


def test_rejects_session_with_wrong_number_of_exercises():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"].pop()

    with pytest.raises(PlanValidationError, match="exactly 3 exercises"):
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


def test_four_day_plan_requires_upper_lower_ab_order():
    plan = valid_plan(sessions_per_week=4)
    for week in plan["weeks"]:
        for session, title in zip(week["sessions"], ("Upper A", "Lower A", "Upper B", "Lower B")):
            session["title"] = title
    parse_and_validate_plan(json.dumps(plan), sessions_per_week=4, citation_registry=VALID_CITATIONS)

    plan["weeks"][0]["sessions"][1]["title"] = "Upper B"
    with pytest.raises(PlanValidationError, match="Upper A, Lower A, Upper B, Lower B"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=4, citation_registry=VALID_CITATIONS)


def test_rejects_missing_weekly_progression():
    plan = valid_plan()
    del plan["weeks"][1]["progression"]
    with pytest.raises(PlanValidationError, match="invalid shape.*progression"):
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


def test_prefers_returned_exercise_specific_reference_over_generic_reference():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["evidence_refs"] = ["KB-bbbbbbbbbbbb"]
    citations = {
        **VALID_CITATIONS,
        "KB-bbbbbbbbbbbb": {
            "source": "guide.txt",
            "evidence": "Hipertrofia: use 3 a 4 séries de 8 a 12 repetições.",
        },
    }

    with pytest.raises(PlanValidationError, match="exercise-specific evidence"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=citations)
