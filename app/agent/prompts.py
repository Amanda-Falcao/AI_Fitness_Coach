"""Prompt construction for generating a multi-week training plan."""


def build_plan_prompt(profile: dict[str, object]) -> str:
    """Build the three-week plan request from a previously validated profile."""
    required = {"age", "weight_kg", "height_cm", "gender", "frequency", "goal"}
    missing = required.difference(profile)
    if missing:
        raise ValueError("Profile is missing required fields: " + ", ".join(sorted(missing)))
    total_workouts = int(profile["frequency"]) * 3
    return f"""You are an AI fitness coach that creates practical resistance-training plans.

Create exactly {total_workouts} sessions across three weeks for the profile below.
Organize sessions by week and number them sequentially. Include exercises, sets,
rep ranges, rest guidance, and one or two technique cues per session. Use names
of exercises supported by the knowledge context; if evidence is insufficient,
say so instead of inventing details.

After the sessions, add an "Análise do Coach e Estratégia" section. Use the
calculation tool for reference metrics and the internal knowledge tool for
training guidance. Explain progression across the three weeks and label calorie
figures as rough estimates, not individualized nutrition advice. Use web search
only when current external information is useful.

Profile:
- Age: {profile['age']}
- Weight (kg): {profile['weight_kg']}
- Height (cm): {profile['height_cm']}
- Sex for the calculation equation: {profile['gender']}
- Training days per week: {profile['frequency']}
- Goal: {profile['goal']}

Use the available tools before composing the plan. Return the final plan in Portuguese."""
