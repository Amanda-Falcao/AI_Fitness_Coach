"""Command-line application for generating a fitness training plan."""

import argparse
import logging
from pathlib import Path

from app.agent.graph import DEFAULT_RECURSION_LIMIT
from app.agent.prompts import build_plan_prompt
from app.config.settings import Settings
from app.rag.ingestion import resolve_project_path
from app.runtime import build_agent_application
from app.tools.calculations import calculate_fitness_metrics


logger = logging.getLogger(__name__)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a three-week fitness training plan.")
    parser.add_argument("--age", type=int, required=True)
    parser.add_argument("--weight-kg", type=float, required=True)
    parser.add_argument("--height-cm", type=float, required=True)
    parser.add_argument("--gender", choices=("male", "female"), required=True)
    parser.add_argument("--frequency", type=int, required=True, help="Training days per week (0-7).")
    parser.add_argument("--goal", required=True, help="For example: hipertrofia, emagrecimento, or manutenção.")
    parser.add_argument("--output", default="outputs/plano_de_treino_final.md")
    return parser


def validate_profile(args: argparse.Namespace) -> dict[str, object]:
    """Validate the CLI profile through the same deterministic calculation contract."""
    calculate_fitness_metrics(
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
    }


def run_plan_generation(profile: dict[str, object], graph, output_path: str | Path) -> Path:
    """Invoke an injected graph and save its final response as Markdown."""
    prompt = build_plan_prompt(profile)
    result = graph.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": DEFAULT_RECURSION_LIMIT},
    )
    messages = result.get("messages", [])
    if not messages:
        raise RuntimeError("Agent completed without returning any messages")
    content = getattr(messages[-1], "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Agent returned an empty or unsupported final response")

    destination = resolve_project_path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    logger.info("Training plan saved to %s", destination)
    return destination


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("python-dotenv is required to load the .env file") from exc
    load_dotenv()

    parser = create_argument_parser()
    args = parser.parse_args()
    profile = validate_profile(args)
    settings = Settings.from_env(require_groq=True, require_tavily=True)
    graph = build_agent_application(settings)
    destination = run_plan_generation(profile, graph, args.output)
    print(f"Training plan saved to {destination}")


if __name__ == "__main__":
    main()
