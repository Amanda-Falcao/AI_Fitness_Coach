"""Command-line application for generating a fitness training plan."""

import argparse
import logging
from pathlib import Path
import time

from app.agent.graph import DEFAULT_RECURSION_LIMIT
from app.agent.plan_output import normalize_groq_plan, parse_and_validate_plan, render_plan_markdown
from app.agent.prompts import build_plan_prompt
from app.config.settings import Settings
from app.observability import aggregate_token_usage, configure_json_logging
from app.rag.citations import citation_registry_from_messages
from app.rag.ingestion import resolve_project_path
from app.runtime import build_agent_application
from app.tools.calculations import calculate_fitness_metrics, format_fitness_metrics


logger = logging.getLogger(__name__)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a three-week fitness training plan.")
    parser.add_argument("--age", type=int, required=True)
    parser.add_argument("--weight-kg", type=float, required=True)
    parser.add_argument("--height-cm", type=float, required=True)
    parser.add_argument("--gender", choices=("male", "female"), required=True)
    parser.add_argument("--frequency", type=int, required=True, help="Training days per week (1-7).")
    parser.add_argument("--goal", required=True, help="For example: hipertrofia, emagrecimento, or manutenção.")
    parser.add_argument("--output", default="outputs/plano_teste_atualizado.md")
    parser.add_argument(
        "--web-search",
        action="store_true",
        help="Enable optional Tavily search; this may use your separate Tavily free quota.",
    )
    return parser


def validate_profile(args: argparse.Namespace) -> dict[str, object]:
    """Validate the CLI profile through the same deterministic calculation contract."""
    if isinstance(args.frequency, bool) or not isinstance(args.frequency, int) or not 1 <= args.frequency <= 7:
        raise ValueError("frequency must be an integer between 1 and 7 for a training plan")
    metrics = calculate_fitness_metrics(
        age_years=args.age,
        weight_kg=args.weight_kg,
        height_cm=args.height_cm,
        sex=args.gender,
        training_days_per_week=args.frequency,
        goal=args.goal,
    )
    return {
        "age": args.age,
        "weight_kg": args.weight_kg,
        "height_cm": args.height_cm,
        "gender": args.gender,
        "frequency": args.frequency,
        "goal": args.goal,
        "reference_metrics": format_fitness_metrics(metrics, args.goal),
    }


def run_plan_generation(
    profile: dict[str, object], graph, output_path: str | Path, *, model_name: str | None = None
) -> Path:
    """Invoke an injected graph and save its final response as Markdown."""
    started_at = time.perf_counter()
    prompt = build_plan_prompt(profile, web_search_enabled=bool(profile.get("web_search_enabled", False)))
    recursion_limit = 6 if profile.get("web_search_enabled", False) else DEFAULT_RECURSION_LIMIT
    try:
        result = graph.invoke(
            {
                "messages": [{"role": "user", "content": prompt}],
                "sessions_per_week": int(profile["frequency"]),
            },
            config={"recursion_limit": recursion_limit},
        )
    except Exception as exc:
        logger.error(
            "Agent invocation failed",
            extra={
                "event": "agent.plan_generation_failed",
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "error_type": type(exc).__name__,
            },
        )
        if type(exc).__name__ == "RateLimitError":
            raise RuntimeError(
                "Groq rate limit reached (HTTP 429); wait for the free-tier limit window to reset before retrying"
            ) from None
        raise RuntimeError(
            f"Agent invocation failed ({type(exc).__name__}); check service availability and configuration"
        ) from None
    messages = result.get("messages", [])
    if not messages:
        raise RuntimeError("Agent completed without returning any messages")
    raw_content = getattr(messages[-1], "content", None)
    try:
        citation_registry = citation_registry_from_messages(messages)
        normalized_content = normalize_groq_plan(
            raw_content, sessions_per_week=int(profile["frequency"])
        )
        plan = parse_and_validate_plan(
            normalized_content,
            sessions_per_week=int(profile["frequency"]),
            citation_registry=citation_registry,
        )
    except (TypeError, ValueError) as exc:
        logger.error("Generated plan failed output validation: %s", exc)
        raise RuntimeError(f"Generated plan did not satisfy the output contract: {exc}") from exc
    content = render_plan_markdown(plan, citation_registry)

    destination = resolve_project_path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    logger.info(
        "Training plan generated and saved",
        extra={
            "event": "agent.plan_generation_completed",
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "session_count": int(profile["frequency"]) * 3,
            "model_name": model_name,
            "token_usage": aggregate_token_usage(messages),
            "output_path": str(destination),
        },
    )
    return destination


def main() -> None:
    configure_json_logging()
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("python-dotenv is required to load the .env file") from exc
    load_dotenv()

    parser = create_argument_parser()
    args = parser.parse_args()
    profile = validate_profile(args)
    profile["web_search_enabled"] = args.web_search
    settings = Settings.from_env(require_groq=True, require_tavily=args.web_search)
    graph = build_agent_application(settings, enable_web_search=args.web_search)
    destination = run_plan_generation(
        profile, graph, args.output, model_name=settings.groq_model_name
    )
    print(f"Training plan saved to {destination}")


if __name__ == "__main__":
    main()
