"""Validated, deterministic fitness calculations.

The calorie estimate is a rough planning aid, not medical or nutrition advice.
It uses the Mifflin-St Jeor equation and an activity multiplier selected from
weekly training frequency, followed by a simple goal adjustment.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FitnessMetrics:
    bmi: float
    basal_metabolic_rate_kcal: float
    estimated_daily_energy_kcal: float
    estimated_target_kcal: float


def _validate_profile(
    age_years: int,
    weight_kg: float,
    height_cm: float,
    sex: str,
    training_days_per_week: int,
) -> str:
    if isinstance(age_years, bool) or not isinstance(age_years, int) or not 13 <= age_years <= 120:
        raise ValueError("age_years must be an integer between 13 and 120")
    if isinstance(weight_kg, bool) or not isinstance(weight_kg, (int, float)) or not 25 <= weight_kg <= 350:
        raise ValueError("weight_kg must be between 25 and 350")
    if isinstance(height_cm, bool) or not isinstance(height_cm, (int, float)) or not 100 <= height_cm <= 250:
        raise ValueError("height_cm must be between 100 and 250")
    if isinstance(training_days_per_week, bool) or not isinstance(training_days_per_week, int) or not 0 <= training_days_per_week <= 7:
        raise ValueError("training_days_per_week must be an integer between 0 and 7")

    normalized_sex = sex.strip().lower() if isinstance(sex, str) else ""
    if normalized_sex not in {"male", "female"}:
        raise ValueError("sex must be 'male' or 'female' for this equation")
    return normalized_sex


def calculate_fitness_metrics(
    *,
    age_years: int,
    weight_kg: float,
    height_cm: float,
    sex: str,
    training_days_per_week: int,
    goal: str,
) -> FitnessMetrics:
    """Calculate BMI, BMR, a rough daily energy estimate, and a goal target.

    The activity multipliers and ±400 kcal goal adjustment preserve the
    prototype's heuristic while making its assumptions explicit and validated.
    They should not be presented as individualized clinical guidance.
    """
    normalized_sex = _validate_profile(
        age_years, weight_kg, height_cm, sex, training_days_per_week
    )
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must be a non-empty string")

    height_m = height_cm / 100
    bmi = weight_kg / (height_m**2)
    sex_constant = 5 if normalized_sex == "male" else -161
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + sex_constant

    activity_multiplier = 1.2 if training_days_per_week == 0 else (
        1.375 if training_days_per_week <= 3 else 1.55
    )
    daily_energy = bmr * activity_multiplier

    normalized_goal = goal.strip().casefold()
    if "emagrecimento" in normalized_goal or "weight loss" in normalized_goal:
        target = daily_energy - 400
    elif "hipertrofia" in normalized_goal or "muscle gain" in normalized_goal:
        target = daily_energy + 400
    else:
        target = daily_energy

    return FitnessMetrics(
        bmi=round(bmi, 2),
        basal_metabolic_rate_kcal=round(bmr),
        estimated_daily_energy_kcal=round(daily_energy),
        estimated_target_kcal=round(target),
    )


def format_fitness_metrics(metrics: FitnessMetrics, goal: str) -> str:
    """Render metrics in the concise format consumed by the agent prompt."""
    return (
        "Reference calculations (estimates):\n"
        f"- BMI: {metrics.bmi:.2f}\n"
        f"- Basal metabolic rate: {metrics.basal_metabolic_rate_kcal} kcal/day\n"
        f"- Estimated daily energy: {metrics.estimated_daily_energy_kcal} kcal/day\n"
        f"- Estimated target for '{goal}': {metrics.estimated_target_kcal} kcal/day"
    )
