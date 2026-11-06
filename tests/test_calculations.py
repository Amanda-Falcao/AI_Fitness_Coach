import pytest

from app.tools.calculations import calculate_fitness_metrics, format_fitness_metrics


def test_calculates_female_profile_and_hypertrophy_target():
    result = calculate_fitness_metrics(
        age_years=28,
        weight_kg=60,
        height_cm=164,
        sex="female",
        training_days_per_week=5,
        goal="hipertrofia",
    )

    assert result.bmi == 22.31
    assert result.basal_metabolic_rate_kcal == 1324
    assert result.estimated_daily_energy_kcal == 2052
    assert result.estimated_target_kcal == 2452


def test_goal_matching_is_case_insensitive_and_format_is_explicit_about_estimates():
    result = calculate_fitness_metrics(
        age_years=30,
        weight_kg=75,
        height_cm=180,
        sex=" MALE ",
        training_days_per_week=3,
        goal="WEIGHT LOSS",
    )

    rendered = format_fitness_metrics(result, "WEIGHT LOSS")
    assert result.estimated_target_kcal == result.estimated_daily_energy_kcal - 400
    assert "estimates" in rendered
    assert "Basal metabolic rate" in rendered


@pytest.mark.parametrize(
    "profile, message",
    [
        ({"age_years": 12}, "age_years"),
        ({"weight_kg": 0}, "weight_kg"),
        ({"height_cm": 0}, "height_cm"),
        ({"sex": "unknown"}, "sex"),
        ({"training_days_per_week": 8}, "training_days_per_week"),
        ({"goal": "  "}, "goal"),
    ],
)
def test_rejects_invalid_profile_values(profile, message):
    values = {
        "age_years": 28,
        "weight_kg": 60,
        "height_cm": 164,
        "sex": "female",
        "training_days_per_week": 5,
        "goal": "hipertrofia",
    }
    values.update(profile)

    with pytest.raises(ValueError, match=message):
        calculate_fitness_metrics(**values)
