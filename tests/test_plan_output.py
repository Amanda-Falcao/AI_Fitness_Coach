import json

import pytest

from app.agent.plan_output import (
    PlanValidationError,
    groq_plan_response_format,
    normalize_groq_plan,
    parse_and_validate_plan,
    render_plan_markdown,
)


EXERCISES = {
    "Supino Reto (Barra)": ("Superior", "Mantenha escápulas estáveis."),
    "Remada Curvada (Barra)": ("Superior", "Puxe em direção ao abdômen."),
    "Desenvolvimento Militar": ("Superior", "Contraia abdômen e glúteos."),
    "Agachamento Livre (Barra)": ("Inferior", "Mantenha a coluna neutra."),
    "Levantamento Terra (Deadlift)": ("Inferior", "Mantenha a barra próxima ao corpo."),
    "Levantamento Terra Romeno": ("Inferior", "Leve o quadril para trás."),
    "Avanço Reverso": ("Inferior", "Dê um passo para trás com controle."),
    "Flexão de Braços": ("Superior", "Mantenha o tronco alinhado."),
}
GENERIC_REF = "KB-000000000000"
EXERCISE_REFS = {name: f"KB-{index:012x}" for index, name in enumerate(EXERCISES, 1)}
VALID_CITATIONS = {
    GENERIC_REF: {
        "source": "dados/conhecimento_fitness.txt",
        "evidence": "Hipertrofia\nSéries/Repetições: 3 a 4 séries, 8 a 12 repetições.\nDescanso: 60 a 90 segundos.",
    },
    **{
        EXERCISE_REFS[name]: {
            "source": "dados/conhecimento_fitness.txt",
            "evidence": f"### {name}\nRegião: {region}.\nMúsculos: {'Peitoral, tríceps e deltoide' if region == 'Superior' else 'Quadríceps e glúteos'}.\nDicas: {cue}",
        }
        for name, (region, cue) in EXERCISES.items()
    },
}


def valid_plan(sessions_per_week=2):
    weeks = []
    for week in range(1, 4):
        sessions = []
        for index in range(sessions_per_week):
            title = f"Treino {index + 1}"
            names = list(EXERCISES)[:3]
            if sessions_per_week == 4:
                title = ("Upper A", "Lower A", "Upper B", "Lower B")[index]
                names = list(EXERCISES)[:3] if index in (0, 2) else list(EXERCISES)[3:6]
            sessions.append({
                "day": index + 1,
                "title": title,
                "exercises": [{
                    "name": name,
                    "sets": 3,
                    "reps": "8-12",
                    "rest_seconds": 90,
                    "technique_cues": ["LLM cue will be replaced"],
                    "evidence_refs": [EXERCISE_REFS[name]],
                } for name in names],
            })
        weeks.append({"week": week, "progression": "model text", "sessions": sessions})
    return {
        "title": "Plano de três semanas",
        "weeks": weeks,
        "coach_analysis": "Aumente gradualmente mantendo a técnica.",
        "safety": {
            "disclaimer": "Plano informativo.",
            "stop_conditions": ["Interrompa se sentir dor aguda."],
            "seek_professional_if": ["Procure profissional em caso de lesão."],
        },
    }


def test_groq_response_schema_leaves_progression_and_cues_deterministic():
    schema = groq_plan_response_format(4)["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert "week_1_progression" not in schema["required"]
    exercise = schema["$defs"]["exercise"]
    assert "technique_cue" not in exercise["required"]
    assert "evidence_ref" in exercise["required"]
    assert schema["$defs"]["session"]["properties"]["day"]["enum"] == list(range(1, 8))
    assert schema["properties"]["week_1_session_1"] == {"$ref": "#/$defs/session"}
    assert len(json.dumps(schema, separators=(",", ":"))) < 3_000


@pytest.mark.parametrize("value", ["8-12", "8–12", "8—12", "8 a 12", "8-12 reps", "8–12 repetições"])
def test_accepts_documented_rep_range_formats(value):
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["reps"] = value
    parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


@pytest.mark.parametrize("value", ["8", "8 até 12", "8-12 séries", "12-8", "7-12", "8-13"])
def test_rejects_invalid_or_undocumented_rep_ranges_with_received_value(value):
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["reps"] = value
    with pytest.raises(PlanValidationError) as error:
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)
    assert repr(value) in str(error.value)


def test_normalize_groq_plan_supplies_fixed_progression():
    raw = {"title": "Plano", "coach_analysis": "Ok", "safety": {
        "disclaimer": "Informativo", "stop_conditions": ["Pare se doer"],
        "seek_professional_if": ["Em caso de lesão"],
    }}
    for week in range(1, 4):
        raw[f"week_{week}_session_1"] = {"day": week, "title": "Treino", **{
            f"exercise_{i}": {"name": "Supino Reto", "sets": 3, "reps": "8-12",
                              "rest_seconds": 90, "evidence_ref": EXERCISE_REFS["Supino Reto (Barra)"]}
            for i in range(1, 4)
        }}
    result = json.loads(normalize_groq_plan(json.dumps(raw), 1))
    assert "Semana 1" in result["weeks"][0]["progression"]
    assert result["weeks"][0]["sessions"][0]["exercises"][0]["technique_cues"] == []


def test_validates_split_stable_ranges_and_renders_tables_once_with_exact_cues():
    plan = parse_and_validate_plan(json.dumps(valid_plan(4)), sessions_per_week=4, citation_registry=VALID_CITATIONS)
    markdown = render_plan_markdown(plan, VALID_CITATIONS)
    assert markdown.count("### Sessão") == 12
    assert markdown.count("## Semana") == 3
    assert markdown.count("| Exercício | Séries | Repetições | Descanso | Referência |") == 12
    assert markdown.count("Mantenha escápulas estáveis.") == 1
    assert "LLM cue will be replaced" not in markdown
    assert "## Guia de execução" in markdown
    assert "## Fontes da base de conhecimento" in markdown
    assert "**Progressão:** Semana 1" in markdown


def test_rejects_four_day_full_body_or_wrong_region_despite_correct_titles():
    plan = valid_plan(4)
    plan["weeks"][0]["sessions"][1]["exercises"] = plan["weeks"][0]["sessions"][0]["exercises"]
    with pytest.raises(PlanValidationError, match="outside the inferior region"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=4, citation_registry=VALID_CITATIONS)


def test_rejects_wrong_title_order_and_undocumented_exercise():
    plan = valid_plan(4)
    plan["weeks"][0]["sessions"][1]["title"] = "Full Body"
    with pytest.raises(PlanValidationError, match="Upper A, Lower A, Upper B, Lower B"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=4, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["name"] = "Leg Press"
    with pytest.raises(PlanValidationError, match="no retrieved exercise-specific section"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_generic_reference_cannot_support_a_specific_exercise():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["evidence_refs"] = [GENERIC_REF]
    with pytest.raises(PlanValidationError, match="no retrieved exercise-specific section"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_muscle_list_is_checked_against_the_declared_region():
    plan = valid_plan()
    squat_ref = EXERCISE_REFS["Agachamento Livre (Barra)"]
    citations = {**VALID_CITATIONS, squat_ref: {
        **VALID_CITATIONS[squat_ref],
        "evidence": "### Agachamento Livre (Barra)\nRegião: Inferior.\nMúsculos: Peitoral e tríceps.\nDicas: Mantenha controle.",
    }}
    plan["weeks"][0]["sessions"][0]["exercises"] = [{
        **exercise, "name": "Agachamento Livre (Barra)", "evidence_refs": [squat_ref]
    } for exercise in plan["weeks"][0]["sessions"][0]["exercises"]]
    with pytest.raises(PlanValidationError, match="conflicts with its documented Músculos"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=citations)


def test_romanian_deadlift_cannot_borrow_deadlift_section():
    plan = valid_plan()
    exercise = plan["weeks"][0]["sessions"][0]["exercises"][0]
    exercise["name"] = "Levantamento Terra Romeno"
    exercise["evidence_refs"] = [EXERCISE_REFS["Levantamento Terra (Deadlift)"]]
    with pytest.raises(PlanValidationError, match="no retrieved exercise-specific section"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_overwrites_model_cue_from_its_own_section_and_rejects_out_of_range_values():
    plan = parse_and_validate_plan(json.dumps(valid_plan()), sessions_per_week=2, citation_registry=VALID_CITATIONS)
    assert plan["weeks"][0]["sessions"][0]["exercises"][0]["technique_cues"] == [EXERCISES["Supino Reto (Barra)"][1]]

    invalid = valid_plan()
    invalid["weeks"][0]["sessions"][0]["exercises"][0]["rest_seconds"] = 120
    with pytest.raises(PlanValidationError, match="outside the documented hypertrophy ranges"):
        parse_and_validate_plan(json.dumps(invalid), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_rejects_changes_to_sets_reps_rest_or_exercises_across_weeks():
    plan = valid_plan()
    plan["weeks"][2]["sessions"][0]["exercises"][0]["sets"] = 4
    with pytest.raises(PlanValidationError, match="stable across weeks"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_preserves_completeness_safety_day_and_schema_checks():
    plan = valid_plan()
    plan["weeks"][1]["sessions"].pop()
    with pytest.raises(PlanValidationError, match="exactly 2 sessions"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"].pop()
    with pytest.raises(PlanValidationError, match="exactly 3 exercises"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["sets"] = 0
    with pytest.raises(PlanValidationError, match="sets must be an integer"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["safety"]["stop_conditions"] = []
    with pytest.raises(PlanValidationError, match="stop_conditions"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["weeks"][0]["sessions"][1]["day"] = 1
    with pytest.raises(PlanValidationError, match="repeats a training day"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["weeks"][0]["week"] = True
    with pytest.raises(PlanValidationError, match="integer between"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)

    plan = valid_plan()
    plan["unexpected"] = "field"
    with pytest.raises(PlanValidationError, match="unexpected: unexpected"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


def test_four_day_upper_session_rejects_lower_exercises_and_requires_order():
    plan = valid_plan(4)
    plan["weeks"][0]["sessions"][0]["exercises"] = plan["weeks"][0]["sessions"][1]["exercises"]
    with pytest.raises(PlanValidationError, match="outside the superior region"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=4, citation_registry=VALID_CITATIONS)

    plan = valid_plan(4)
    plan["weeks"][0]["sessions"][1]["title"] = "Upper B"
    with pytest.raises(PlanValidationError, match="Upper A, Lower A, Upper B, Lower B"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=4, citation_registry=VALID_CITATIONS)


def test_rejects_reference_id_not_returned_by_rag():
    plan = valid_plan()
    plan["weeks"][0]["sessions"][0]["exercises"][0]["evidence_refs"] = ["KB-bbbbbbbbbbbb"]
    with pytest.raises(PlanValidationError, match="not returned by the RAG tool"):
        parse_and_validate_plan(json.dumps(plan), sessions_per_week=2, citation_registry=VALID_CITATIONS)


@pytest.mark.parametrize("response", ["not json", "```json\n{}\n```"])
def test_rejects_invalid_json(response):
    with pytest.raises(PlanValidationError, match="valid JSON"):
        parse_and_validate_plan(response, sessions_per_week=2)
