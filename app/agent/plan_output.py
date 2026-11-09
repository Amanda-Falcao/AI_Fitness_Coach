"""Validate the agent's JSON plan contract and render it as readable Markdown."""

import json
import re
import unicodedata
from typing import Any


_REFERENCE_PATTERN = re.compile(r"^KB-[0-9a-f]{12}$")
_WEEKLY_PROGRESSIONS = (
    "Semana 1: estabeleça uma referência com boa execução e aproximadamente 1–2 RIR.",
    "Semana 2: priorize aumentar repetições dentro da faixa somente se todas as séries forem concluídas com boa técnica; caso contrário, mantenha a meta.",
    "Semana 3: aumente a carga somente se o limite superior da faixa for alcançado em todas as séries com boa execução; caso contrário, mantenha a carga e continue progredindo repetições.",
)


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


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
    training_day = {"type": "integer", "enum": list(range(1, 8))}
    exercise = closed_object({
        "name": text,
        "sets": {"type": "integer"},
        "reps": text,
        "rest_seconds": {"type": "integer"},
        "evidence_ref": text,
    })
    session = closed_object({
        "day": training_day,
        "title": text,
        **{
            f"exercise_{index}": {"$ref": "#/$defs/exercise"}
            for index in range(1, 4)
        },
    })
    safety = closed_object({
        "disclaimer": text,
        "stop_conditions": {"type": "array", "items": text},
        "seek_professional_if": {"type": "array", "items": text},
    })
    schema = closed_object({
        "title": text,
        **{
            f"week_{week}_session_{session_number}": {"$ref": "#/$defs/session"}
            for week in range(1, 4)
            for session_number in range(1, sessions_per_week + 1)
        },
        "coach_analysis": text,
        "safety": safety,
    })
    schema["$defs"] = {"exercise": exercise, "session": session}
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
                        "technique_cues": [],
                        "evidence_refs": [exercise["evidence_ref"]],
                    })
                sessions.append({
                    "day": session["day"],
                    "title": session["title"],
                    "exercises": exercises,
                })
            weeks.append({
                "week": week_number,
                "progression": _WEEKLY_PROGRESSIONS[week_number - 1],
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
        raise PlanValidationError(
            f"{field} must be an integer between {minimum} and {maximum}; received {value!r}"
        )
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


def _exercise_section(name: str, references: list[str], registry: dict[str, dict[str, str]]):
    normalized_name = _normalized_text(name)
    for reference in references:
        citation = registry.get(reference)
        if not citation:
            continue
        evidence = citation["evidence"]
        normalized = _normalized_text(evidence)
        heading = re.search(r"(?m)^###\s+(.+?)\s*$", evidence)
        if not heading:
            continue
        heading_title = _normalized_text(heading.group(1))
        parenthetical = re.search(r"\(([^()]*)\)\s*$", heading.group(1))
        base_title = _normalized_text(re.sub(r"\s*\([^()]*\)\s*$", "", heading.group(1)))
        names_in_heading = {heading_title, base_title}
        if parenthetical:
            names_in_heading.add(_normalized_text(parenthetical.group(1)))
        if normalized_name not in names_in_heading:
            continue
        # Exercise evidence must be a discrete section containing its own
        # title, muscle region, muscles, and documented cue.
        if all(
            marker in normalized for marker in ("regiao:", "musculos:", "dicas:")
        ):
            return reference, evidence
    return None, None


def _range_pair(value: str, field: str) -> tuple[int, int]:
    match = re.fullmatch(
        r"\s*(\d+)\s*(?:-|–|—|a)\s*(\d+)\s*(?:(?:reps|repeti[cç][oõ]es))?\s*",
        value,
        re.IGNORECASE,
    )
    if not match:
        raise PlanValidationError(
            f"{field} must be a documented numeric range; received {value!r}"
        )
    low, high = map(int, match.groups())
    if low > high:
        raise PlanValidationError(f"{field} has an inverted range; received {value!r}")
    return low, high


def _documented_hypertrophy_ranges(registry: dict[str, dict[str, str]]):
    for citation in registry.values():
        text = citation["evidence"]
        if "hipertrofia" not in _normalized_text(text):
            continue
        match = re.search(
            r"(\d+)\s*a\s*(\d+)\s*s[eé]ries\s*,\s*(\d+)\s*a\s*(\d+)\s*repeti[cç][oõ]es.*?(\d+)\s*a\s*(\d+)\s*segundos",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return tuple(map(int, match.groups()))
    raise PlanValidationError("Retrieved knowledge does not document hypertrophy sets, reps, and rest ranges")


def _region(evidence: str) -> str:
    muscles = re.search(r"(?im)^Músculos:\s*(.+)$", evidence)
    declared = re.search(r"(?im)^Região:\s*(Superior|Inferior)\s*\.", evidence)
    if not muscles or not declared:
        raise PlanValidationError("Exercise section must document its region and muscles")
    text = _normalized_text(muscles.group(1))
    upper_markers = ("peitoral", "peito", "dorsal", "latissimo", "biceps", "triceps", "deltoid", "ombro", "trapezio", "braco")
    lower_markers = ("quadriceps", "glute", "isquiotib", "coxa", "perna", "panturrilha")
    has_upper = any(marker in text for marker in upper_markers)
    has_lower = any(marker in text for marker in lower_markers)
    if has_upper == has_lower:
        raise PlanValidationError("Músculos do exercício do not identify one clear upper/lower region")
    inferred = "superior" if has_upper else "inferior"
    if _normalized_text(declared.group(1)) != inferred:
        raise PlanValidationError("Declared exercise region conflicts with its documented Músculos")
    return inferred


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
    sets_min, sets_max, reps_min, reps_max, rest_min, rest_max = _documented_hypertrophy_ranges(citation_registry)
    weeks = plan.get("weeks")
    if not isinstance(weeks, list) or len(weeks) != 3:
        raise PlanValidationError("Plan must contain exactly three weeks")

    for week_index, week in enumerate(weeks, start=1):
        _require_keys(week, {"week", "progression", "sessions"}, f"week {week_index}")
        week_number = _require_integer(week.get("week"), f"week {week_index}.week", 1, 3)
        if week_number != week_index:
            raise PlanValidationError(f"Week entries must be numbered sequentially from 1 to 3 (expected {week_index})")
        # Progression text is supplied deterministically below.
        week["progression"] = _WEEKLY_PROGRESSIONS[week_index - 1]
        sessions = week.get("sessions")
        if not isinstance(sessions, list) or len(sessions) != sessions_per_week:
            raise PlanValidationError(
                f"Week {week_index} must contain exactly {sessions_per_week} sessions"
            )
        days = set()
        session_signatures = []
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
            signature = []
            regions = []
            for exercise_index, exercise in enumerate(exercises, start=1):
                exercise_label = f"{label} exercise {exercise_index}"
                _require_keys(
                    exercise,
                    {"name", "sets", "reps", "rest_seconds", "technique_cues", "evidence_refs"},
                    exercise_label,
                )
                _require_text(exercise.get("name"), f"{exercise_label}.name", max_length=120)
                sets = _require_integer(exercise.get("sets"), f"{exercise_label}.sets", 1, 10)
                reps = _require_text(exercise.get("reps"), f"{exercise_label}.reps", max_length=80)
                rest = _require_integer(exercise.get("rest_seconds"), f"{exercise_label}.rest_seconds", 0, 600)
                rep_low, rep_high = _range_pair(reps, f"{exercise_label}.reps")
                if not sets_min <= sets <= sets_max or not reps_min <= rep_low <= rep_high <= reps_max or not rest_min <= rest <= rest_max:
                    raise PlanValidationError(f"{exercise_label} prescription is outside the documented hypertrophy ranges")
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
                evidence_ref, evidence = _exercise_section(exercise["name"], references, citation_registry)
                if evidence is None:
                    raise PlanValidationError(f"{exercise_label} has no retrieved exercise-specific section")
                cue_match = re.search(r"(?im)^Dicas:\s*(.+)$", evidence)
                if not cue_match:
                    raise PlanValidationError(f"{exercise_label} section has no documented technique cue")
                exercise["technique_cues"] = [cue_match.group(1).strip()]
                exercise["evidence_refs"] = [evidence_ref]
                regions.append(_region(evidence))
                signature.append((_normalized_text(exercise["name"]), sets, rep_low, rep_high, rest))
            session_signatures.append((session["day"], session["title"], signature))
            if sessions_per_week == 4:
                expected_region = "inferior" if session_index in (2, 4) else "superior"
                if any(region != expected_region for region in regions):
                    raise PlanValidationError(f"{label} contains an exercise outside the {expected_region} region")
        if sessions_per_week == 4:
            expected_titles = ["upper a", "lower a", "upper b", "lower b"]
            if [session["title"].strip().casefold() for session in sessions] != expected_titles:
                raise PlanValidationError(
                    f"Week {week_index} must use the Upper A, Lower A, Upper B, Lower B split"
                )
        if week_index == 1:
            first_week_signature = session_signatures
        elif session_signatures != first_week_signature:
            raise PlanValidationError("Session split and exercise prescriptions must remain stable across weeks")

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
        lines.extend([f"## Semana {week['week']}", "", f"**Progressão:** {week['progression']}", ""])
        for index, session in enumerate(week["sessions"], start=1):
            lines.extend([f"### Sessão {index} — {session['title']} (Dia {session['day']})", ""])
            lines.extend(["| Exercício | Séries | Repetições | Descanso | Referência |", "|---|---:|---:|---:|---|"])
            for exercise in session["exercises"]:
                lines.append(
                    f"| {exercise['name']} | {exercise['sets']} | {exercise['reps']} | "
                    f"{exercise['rest_seconds']} s | {', '.join(exercise['evidence_refs'])} |"
                )
            lines.append("")

    lines.extend(["## Guia de execução", ""])
    cue_by_exercise = {}
    for week in plan["weeks"][:1]:
        for session in week["sessions"]:
            for exercise in session["exercises"]:
                cue_by_exercise[exercise["name"]] = exercise["technique_cues"][0]
    lines.extend(f"- **{name}:** {cue}" for name, cue in cue_by_exercise.items())
    lines.append("")

    lines.extend(["## Fontes da base de conhecimento", ""])
    used_references = {
        reference
        for week in plan["weeks"]
        for session in week["sessions"]
        for exercise in session["exercises"]
        for reference in exercise["evidence_refs"]
    }
    exercise_names_by_reference: dict[str, list[str]] = {}
    for week in plan["weeks"]:
        for session in week["sessions"]:
            for exercise in session["exercises"]:
                for reference in exercise["evidence_refs"]:
                    names = exercise_names_by_reference.setdefault(reference, [])
                    if exercise["name"] not in names:
                        names.append(exercise["name"])
    for reference in sorted(used_references):
        citation = citation_registry[reference]
        # Technique cues already appear once in the execution guide. Keep the
        # reference focused on the same section's identity and target muscles.
        evidence = "\n".join(
            line for line in citation["evidence"].strip().splitlines()
            if not line.startswith("Dicas:")
        )
        names = ", ".join(exercise_names_by_reference[reference])
        lines.append(f"- **{names} — [{reference}]** `{citation['source']}`\n\n{evidence}")

    lines.extend(["", "## Análise do Coach e Estratégia", "", plan["coach_analysis"], "", "## Segurança", ""])
    lines.extend([f"- {plan['safety']['disclaimer']}", "", "**Pare se:**"])
    lines.extend(f"- {condition}" for condition in plan["safety"]["stop_conditions"])
    lines.extend(["", "**Procure orientação profissional se:**"])
    lines.extend(f"- {condition}" for condition in plan["safety"]["seek_professional_if"])
    return "\n".join(lines) + "\n"
