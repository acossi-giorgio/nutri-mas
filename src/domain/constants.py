from __future__ import annotations

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
MEAL_SLOTS = ("breakfast", "morning_snack", "lunch", "afternoon_snack", "dinner")
SLOT_WEIGHTS = {
    "breakfast": 0.24,
    "morning_snack": 0.10,
    "lunch": 0.29,
    "afternoon_snack": 0.10,
    "dinner": 0.27,
}
MEAL_TIMES_MINUTES = {
    "breakfast": 540,
    "morning_snack": 630,
    "lunch": 780,
    "afternoon_snack": 990,
    "dinner": 1200,
}
NEXT_MEAL_SLOTS = {
    "breakfast": "morning_snack",
    "morning_snack": "lunch",
    "lunch": "afternoon_snack",
    "afternoon_snack": "dinner",
}
RECIPE_MEAL_SLOTS = (
    ("breakfast", "breakfast"),
    ("snack", "morning_snack"),
    ("snack", "afternoon_snack"),
    ("main_meal", "lunch"),
    ("main_meal", "dinner"),
    ("lunch", "lunch"),
    ("dinner", "dinner"),
)
SLOT_ALLOWED = (("any", slot) for slot in MEAL_SLOTS)
SLOT_ALLOWED = tuple(SLOT_ALLOWED) + RECIPE_MEAL_SLOTS
MEAL_LABELS = {
    "breakfast": "Breakfast",
    "morning_snack": "Morning snack",
    "lunch": "Lunch",
    "afternoon_snack": "Afternoon snack",
    "dinner": "Dinner",
}
WEEKDAY_LABELS = {day: day.capitalize() for day in WEEKDAYS}

ONBOARDING_QUESTIONS = {
    "height": "What is your height in centimetres?",
    "weight": "What is your current weight in kilograms?",
    "age": "How old are you?",
    "sex": "What is your gender? Choose male or female.",
    "activity": (
        "What is your activity level? Choose sedentary, light, moderate, active, "
        "or very active."
    ),
    "allergens": "Do you have any allergies?",
    "diet_type": ("Which diet do you follow? Choose omnivore, vegetarian, or vegan."),
    "culinary_preferences": (
        "Do you have culinary preferences or special recipe requests?"
    ),
}


def slot_index(slot: str) -> int:
    """Return the ordered index of a meal slot."""
    return MEAL_SLOTS.index(slot)


def inject_bdi_constants(
    agent: object,
    *,
    schedule: bool = False,
    recipe_slots: bool = False,
    allowed_slots: bool = False,
) -> None:
    """Inject shared constants into a BDI agent."""
    from src.utils.bdi import add_belief_fact

    for slot, weight in SLOT_WEIGHTS.items():
        add_belief_fact(agent, "slot_weight", slot, weight)
    if schedule:
        for slot, minutes in MEAL_TIMES_MINUTES.items():
            add_belief_fact(agent, "meal_time", slot, minutes)
        for slot, next_slot in NEXT_MEAL_SLOTS.items():
            add_belief_fact(agent, "next_meal_slot", slot, next_slot)
    if recipe_slots:
        for recipe_slot, slot in RECIPE_MEAL_SLOTS:
            add_belief_fact(agent, "recipe_meal_slot", recipe_slot, slot)
    if allowed_slots:
        for recipe_slot, slot in SLOT_ALLOWED:
            add_belief_fact(agent, "slot_allowed", recipe_slot, slot)
