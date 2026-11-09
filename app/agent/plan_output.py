"""Validate the agent's JSON plan contract and render it as readable Markdown."""

import json
import re
import unicodedata
from typing import Any


_REFERENCE_PATTERN = re.compile(r"^KB-[0-9a-f]{12}$")
_EXERCISE_ALIASES = {
    "agachamento": ("agachamento", "squat"),
    "supino": ("supino", "bench press"),
    "levantamento terra": ("levantamento terra", "deadlift"),
    "remada curvada": ("remada curvada", "bent row"),
    "desenvolvimento militar": ("desenvolvimento militar", "overhead press"),
}


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def _specific_evidence_terms(exercise_name: str) -> tuple[str, ...]:
    normalized_name = _normalized_text(exercise_name)
    for canonical, aliases in _EXERCISE_ALIASES.items():
        if canonical in normalized_name or any(alias in normalized_name for alias in aliases):
            return aliases
    return (normalized_name,)


class PlanValidationError(ValueError):
    """Raised when an LLM response does not satisfy the training plan contract."""


def groq_plan_response_format(sessions_per_week: int) -> dict[str, Any]:
    """Return a flat strict schema with a required slot for every plan session."""
    _require_integer(sessions_per_week, "sessions_per_week", 1, 7)

    def closed_object(properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    text = {"type": "string"}
    exercise = closed_object({
        "name": text,
        "sets": {"type": "integer"},
        "reps": text,
        "rest_seconds": {"type": "integer"},
        "technique_cue": text,
        "evidence_ref": text,
    })
    session = closed_object({
        "day": {"type": "integer"},
        "title": text,
        **{f"exercise_{index}": exercise for index in range(1, 4)},
    })
    safety = closed_object({
        "disclaimer": text,
        "stop_conditions": {"type": "array", "items": text},
        "seek_professional_if": {"type": "array", "items": text},
    })
    schema = closed_object({
        "title": text,
        **{f"week_{week}_progression": text for week in range(1, 4)},
        **{
            f"week_{week}_session_{session_number}": session
            for week in range(1, 4)
            for session_number in range(1, sessions_per_week + 1)
        },
        "coach_analysis": text,
        "safety": safety,
    })
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "fitness_training_plan",
            "strict": True,
            "schema": schema,
        },
    }


def normalize_groq_plan(raw_content: str, sessions_per_week: int) -> str:
    """Convert flat strict-schema session slots into the stable list-based contract."""
    _require_integer(sessions_per_week, "sessions_per_week", 1, 7)
    try:
        plan = json.loads(raw_content)
        if isinstance(plan.get("weeks"), list):
            return json.dumps(plan, ensure_ascii=False)
        weeks = []
        for week_number in range(1, 4):
            sessions = []
            for session_number in range(1, sessions_per_week + 1):
                slot_name = f"week_{week_number}_session_{session_number}"
                session = plan.pop(slot_name)
                exercises = []
                for exercise_number in range(1, 4):
                    exercise = session.pop(f"exercise_{exercise_number}")
                    exercises.append({
                        "name": exercise["name"],
                        "sets": exercise["sets"],
                        "reps": exercise["reps"],
                        "rest_seconds": exercise["rest_seconds"],
                        "technique_cues": [exercise["technique_cue"]],
                        "evidence_refs": [exercise["evidence_ref"]],
                    })
                sessions.append({
                    "day": session["day"],
                    "title": session["title"],
                    "exercises": exercises,
                })
            weeks.append({
                "week": week_number,
                "progression": plan.pop(f"week_{week_number}_progression"),
                "sessions": sessions,
            })
        plan["weeks"] = weeks
        return json.dumps(plan, ensure_ascii=False)
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PlanValidationError("Agent response does not match the numbered plan schema") from exc


def _require_text(value: Any, field: str, *, max_length: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise PlanValidationError(f"{field} must be a non-empty string up to {max_length} characters")
    return value.strip()


def _require_integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise PlanValidationError(f"{field} must be an integer between {minimum} and {maximum}")
    return value


def _require_keys(value: Any, expected: set[str], field: str) -> None:
    if not isinstance(value, dict):
        raise PlanValidationError(f"{field} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("unexpected: " + ", ".join(extra))
        raise PlanValidationError(f"{field} has an invalid shape ({'; '.join(details)})")


def parse_and_validate_plan(
    raw_content: str,
    *,
    sessions_per_week: int,
    citation_registry: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Parse JSON and validate completeness, exercise fields, and safety content."""
    _require_integer(sessions_per_week, "sessions_per_week", 1, 7)
    citation_registry = citation_registry or {}
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise PlanValidationError("Agent response must be non-empty JSON")
    try:
        plan = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise PlanValidationError("Agent response is not valid JSON; the plan was not saved") from exc
    _require_keys(plan, {"title", "weeks", "coach_analysis", "safety"}, "plan")

    _require_text(plan.get("title"), "title", max_length=160)
    weeks = plan.get("weeks")
    if not isinstance(weeks, list) or len(weeks) != 3:
        raise PlanValidationError("Plan must contain exactly three weeks")

    for week_index, week in enumerate(weeks, start=1):
        _require_keys(week, {"week", "progression", "sessions"}, f"week {week_index}")
        week_number = _require_integer(week.get("week"), f"week {week_index}.week", 1, 3)
        if week_number != week_index:
            raise PlanValidationError(f"Week entries must be numbered sequentially from 1 to 3 (expected {week_index})")
        _require_text(week.get("progression"), f"week {week_index}.progression", max_length=500)
        sessions = week.get("sessions")
        if not isinstance(sessions, list) or len(sessions) != sessions_per_week:
            raise PlanValidationError(
                f"Week {week_index} must contain exactly {sessions_per_week} sessions"
            )
        days = set()
        for session_index, session in enumerate(sessions, start=1):
            label = f"week {week_index} session {session_index}"
            _require_keys(session, {"day", "title", "exercises"}, label)
            day = _require_integer(session.get("day"), f"{label}.day", 1, 7)
            if day in days:
                raise PlanValidationError(f"{label} repeats a training day within its week")
            days.add(day)
            _require_text(session.get("title"), f"{label}.title", max_length=160)
            exercises = session.get("exercises")
            if not isinstance(exercises, list) or len(exercises) != 3:
                raise PlanValidationError(f"{label} must contain exactly 3 exercises")
            for exercise_index, exercise in enumerate(exercises, start=1):
                exercise_label = f"{label} exercise {exercise_index}"
                _require_keys(
                    exercise,
                    {"name", "sets", "reps", "rest_seconds", "technique_cues", "evidence_refs"},
                    exercise_label,
                )
                _require_text(exercise.get("name"), f"{exercise_label}.name", max_length=120)
                _require_integer(exercise.get("sets"), f"{exercise_label}.sets", 1, 10)
                _require_text(exercise.get("reps"), f"{exercise_label}.reps", max_length=80)
                _require_integer(exercise.get("rest_seconds"), f"{exercise_label}.rest_seconds", 0, 600)
                cues = exercise.get("technique_cues")
                if not isinstance(cues, list) or not 1 <= len(cues) <= 2:
                    raise PlanValidationError(f"{exercise_label}.technique_cues must contain one or two cues")
                for cue_index, cue in enumerate(cues, start=1):
                    _require_text(cue, f"{exercise_label}.technique_cues[{cue_index}]", max_length=240)
                references = exercise.get("evidence_refs")
                if not isinstance(references, list) or not 1 <= len(references) <= 3:
                    raise PlanValidationError(f"{exercise_label}.evidence_refs must contain one to three citations")
                for reference in references:
                    if not isinstance(reference, str) or not _REFERENCE_PATTERN.fullmatch(reference):
                        raise PlanValidationError(f"{exercise_label} contains an invalid citation ID")
                    if reference not in citation_registry:
                        raise PlanValidationError(
                            f"{exercise_label} cites evidence that was not returned by the RAG tool: {reference}"
                        )
                specific_terms = _specific_evidence_terms(exercise["name"])
                available_specific_refs = {
                    ref_id
                    for ref_id, citation in citation_registry.items()
                    if any(term in _normalized_text(citation["evidence"]) for term in specific_terms)
                }
                if available_specific_refs and not available_specific_refs.intersection(references):
                    raise PlanValidationError(
                        f"{exercise_label} must cite the retrieved exercise-specific evidence"
                    )

    if sessions_per_week == 4:
        expected_titles = ["upper a", "lower a", "upper b", "lower b"]
        for week_index, week in enumerate(weeks, start=1):
            titles = [session["title"].strip().casefold() for session in week["sessions"]]
            if titles != expected_titles:
                raise PlanValidationError(
                    f"Week {week_index} must use the Upper A, Lower A, Upper B, Lower B split"
                )

    _require_text(plan.get("coach_analysis"), "coach_analysis", max_length=4000)
    safety = plan.get("safety")
    _require_keys(safety, {"disclaimer", "stop_conditions", "seek_professional_if"}, "safety")
    _require_text(safety.get("disclaimer"), "safety.disclaimer", max_length=600)
    for field in ("stop_conditions", "seek_professional_if"):
        items = safety.get(field)
        if not isinstance(items, list) or not 1 <= len(items) <= 6:
            raise PlanValidationError(f"safety.{field} must contain between 1 and 6 items")
        for index, item in enumerate(items, start=1):
            _require_text(item, f"safety.{field}[{index}]", max_length=240)
    return plan


def render_plan_markdown(
    plan: dict[str, Any], citation_registry: dict[str, dict[str, str]]
) -> str:
    """Render a validated plan deterministically for the CLI and notebook."""
    lines = [f"# {plan['title']}", ""]
    for week in plan["weeks"]:
        lines.extend([
            f"## Semana {week['week']}",
            "",
            f"**Progressão:** {week['progression']}",
            "",
        ])
        for index, session in enumerate(week["sessions"], start=1):
            lines.extend([f"### Sessão {index} — {session['title']} (Dia {session['day']})", ""])
            for exercise in session["exercises"]:
                rest = exercise["rest_seconds"]
                lines.append(
                    f"- **{exercise['name']}** — {exercise['sets']} séries × {exercise['reps']} "
                    f"(descanso: {rest}s) — Evidência: {', '.join(exercise['evidence_refs'])}"
                )
                lines.extend(f"  - Técnica: {cue}" for cue in exercise["technique_cues"])
            lines.append("")

    lines.extend(["## Fontes da base de conhecimento", ""])
    used_references = {
        reference
        for week in plan["weeks"]
        for session in week["sessions"]
        for exercise in session["exercises"]
        for reference in exercise["evidence_refs"]
    }
    for reference in sorted(used_references):
        citation = citation_registry[reference]
        evidence = citation["evidence"].replace("\n", " ").strip()
        if len(evidence) > 360:
            evidence = evidence[:357].rstrip() + "..."
        lines.append(f"- **[{reference}]** `{citation['source']}` — {evidence}")

    lines.extend(["", "## Análise do Coach e Estratégia", "", plan["coach_analysis"], "", "## Segurança", ""])
    lines.extend([f"- {plan['safety']['disclaimer']}", "", "**Pare se:**"])
    lines.extend(f"- {condition}" for condition in plan["safety"]["stop_conditions"])
    lines.extend(["", "**Procure orientação profissional se:**"])
    lines.extend(f"- {condition}" for condition in plan["safety"]["seek_professional_if"])
    return "\n".join(lines) + "\n"
