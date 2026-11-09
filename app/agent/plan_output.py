"""Validate the agent's JSON plan contract and render it as readable Markdown."""

import json
import re
from typing import Any


_REFERENCE_PATTERN = re.compile(r"^KB-[0-9a-f]{12}$")


class PlanValidationError(ValueError):
    """Raised when an LLM response does not satisfy the training plan contract."""


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
        _require_keys(week, {"week", "sessions"}, f"week {week_index}")
        week_number = _require_integer(week.get("week"), f"week {week_index}.week", 1, 3)
        if week_number != week_index:
            raise PlanValidationError(f"Week entries must be numbered sequentially from 1 to 3 (expected {week_index})")
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
            if not isinstance(exercises, list) or not 1 <= len(exercises) <= 12:
                raise PlanValidationError(f"{label} must contain between 1 and 12 exercises")
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
        lines.extend([f"## Semana {week['week']}", ""])
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
