"""LangChain adapter for the shared deterministic calculation function."""

from app.tools.calculations import calculate_fitness_metrics, format_fitness_metrics


def create_calculation_tool():
    """Create the model-callable calculation tool on demand."""
    try:
        from langchain_core.tools import tool
    except ImportError as exc:
        raise RuntimeError(
            "LangChain dependencies are missing; install the project requirements"
        ) from exc

    @tool
    def calculate_profile_metrics(
        age_years: int,
        weight_kg: float,
        height_cm: float,
        sex: str,
        training_days_per_week: int,
        goal: str,
    ) -> str:
        """Calculate reference BMI and energy estimates for a fitness profile."""
        metrics = calculate_fitness_metrics(
            age_years=age_years,
            weight_kg=weight_kg,
            height_cm=height_cm,
            sex=sex,
            training_days_per_week=training_days_per_week,
            goal=goal,
        )
        return format_fitness_metrics(metrics, goal)

    return calculate_profile_metrics
