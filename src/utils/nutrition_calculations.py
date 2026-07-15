ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
PROTEIN_FACTORS = {
    "sedentary": 1.0,
    "light": 1.2,
    "moderate": 1.5,
    "active": 1.7,
    "very_active": 2.0,
}
HEALTHY_BMI_MIN = 18.5
HEALTHY_BMI_MAX = 24.9
HEALTHY_BMI_MIDPOINT = (HEALTHY_BMI_MIN + HEALTHY_BMI_MAX) / 2.0
TARGET_WEIGHT_TOLERANCE_KG = 1.0


def _normalized_key(value) -> str:
    """Normalize a lookup key."""
    return str(value or "").strip().lower()


def calculate_profile_targets(
    height, weight, age, sex, activity, goal_override=None
) -> dict[str, float | str]:
    """Calculate nutrition targets, optionally preserving an existing goal."""
    height = float(height)
    weight = float(weight)
    age = int(age)
    activity_key = _normalized_key(activity)
    sex_key = str(sex or "").strip().upper()
    height_m = height / 100.0
    # Use the centre of the configured healthy-BMI interval as a neutral target,
    # with a small maintenance band to avoid changing goal for tiny variations.
    target_weight = HEALTHY_BMI_MIDPOINT * height_m * height_m
    goal = _normalized_key(goal_override)
    if goal not in {"lose", "gain", "maintain"}:
        if weight > target_weight + TARGET_WEIGHT_TOLERANCE_KG:
            goal = "lose"
        elif weight < target_weight - TARGET_WEIGHT_TOLERANCE_KG:
            goal = "gain"
        else:
            goal = "maintain"
    adjustment = {"lose": -300, "gain": 300}.get(goal, 0)
    sex_offset = 5.0 if sex_key == "M" else -161.0
    bmr = 10.0 * weight + 6.25 * height - 5.0 * age + sex_offset
    daily_calories = (
        bmr * ACTIVITY_FACTORS.get(activity_key, ACTIVITY_FACTORS["moderate"])
        + adjustment
    )
    return {
        "daily_calories": int(round(daily_calories)),
        "goal": goal,
        "target_weight": round(target_weight, 1),
    }


def calculate_weight_change_percent(previous_weight, current_weight) -> float:
    """Return the absolute percentage change between consecutive weigh-ins."""
    previous = float(previous_weight)
    current = float(current_weight)
    if previous <= 0 or current <= 0:
        raise ValueError("Weights must be greater than zero")
    return round(abs(current - previous) / previous * 100.0, 2)


def calculate_slot_macro_targets(
    daily_calories, weight, activity, slot_weight
) -> dict[str, int]:
    """Calculate slot macro targets."""
    daily_calories = float(daily_calories)
    weight = float(weight)
    slot_weight = float(slot_weight)
    activity_key = _normalized_key(activity)
    total_protein = weight * PROTEIN_FACTORS.get(
        activity_key, PROTEIN_FACTORS["moderate"]
    )
    protein_calories = total_protein * 4.0
    fat_calories = daily_calories * 0.30
    carbs_calories = max(daily_calories - protein_calories - fat_calories, 0.0)
    return {
        "protein_g": int(round(total_protein * slot_weight)),
        "carbs_g": int(round((carbs_calories / 4.0) * slot_weight)),
        "fat_g": int(round((fat_calories / 9.0) * slot_weight)),
    }


def check_macro_tolerance(
    calories: int,
    protein: int,
    carbs: int,
    fat: int,
    t_cal: float,
    t_pro: float,
    t_carbs: float,
    t_fat: float,
    min_tol: float,
    max_tol: float,
) -> bool:
    """Check macro tolerance."""
    macro_min_tol = 0.80
    macro_max_tol = 1.20
    return (
        t_cal * min_tol <= calories <= t_cal * max_tol
        and t_pro * macro_min_tol <= protein <= t_pro * macro_max_tol
        and t_carbs * macro_min_tol <= carbs <= t_carbs * macro_max_tol
        and t_fat * macro_min_tol <= fat <= t_fat * macro_max_tol
    )


def calculate_rebalance_target(
    daily_budget: float,
    eaten_today: float,
    slot: str,
) -> int:
    """Calculate the remaining calorie target for a meal slot."""
    slot_weights = {
        "breakfast": 0.24,
        "morning_snack": 0.10,
        "lunch": 0.29,
        "afternoon_snack": 0.10,
        "dinner": 0.27,
    }
    order = ["breakfast", "morning_snack", "lunch", "afternoon_snack", "dinner"]
    try:
        current_idx = order.index(slot)
    except ValueError:
        return 0
    remaining_slots = order[current_idx:]
    remaining_weight_sum = sum(slot_weights[s] for s in remaining_slots)
    remaining_cals = max(0.0, float(daily_budget) - float(eaten_today))
    if remaining_weight_sum <= 0:
        return 0
    target = remaining_cals * (slot_weights.get(slot, 0.0) / remaining_weight_sum)
    return int(round(target))


def calculate_rebalance_slot_target(
    daily_budget: float,
    eaten_today: float,
    origin_slot: str,
    target_slot: str,
) -> int:
    """Allocate remaining calories after a modified meal."""
    slot_weights = {
        "breakfast": 0.24,
        "morning_snack": 0.10,
        "lunch": 0.29,
        "afternoon_snack": 0.10,
        "dinner": 0.27,
    }
    order = ["breakfast", "morning_snack", "lunch", "afternoon_snack", "dinner"]
    origin = str(origin_slot or "").strip().lower()
    target = str(target_slot or "").strip().lower()
    try:
        origin_idx = order.index(origin)
    except ValueError:
        return calculate_rebalance_target(daily_budget, eaten_today, target)
    future_slots = order[origin_idx + 1 :]
    if target not in future_slots:
        return 0
    remaining_weight_sum = sum(slot_weights[s] for s in future_slots)
    remaining_cals = max(0.0, float(daily_budget) - float(eaten_today))
    if remaining_weight_sum <= 0:
        return 0
    return int(round(remaining_cals * (slot_weights[target] / remaining_weight_sum)))
