from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict


class Messages(TypedDict):
    """A command the NLP agent may route to an application agent."""

    id: str
    agent: str
    message_performative: str
    name: str
    description: str
    signature: str
    schema: dict[str, Any]


_MEAL_SLOTS = [
    "breakfast",
    "morning_snack",
    "lunch",
    "afternoon_snack",
    "dinner",
    "logged",
]
_WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _message(
    agent: str,
    message_performative: str,
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> Messages:
    """Build one registry entry with a stable, Qdrant-safe identifier."""
    return {
        "id": f"{agent}.{name}",
        "agent": agent,
        "message_performative": message_performative,
        "name": name,
        "description": description,
        "signature": f"{name}({', '.join(properties)})",
        "schema": {
            "functor": name,
            "arity": len(properties),
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


MESSAGES: dict[str, Messages] = {
    "nutritionist.answer": _message(
        "nutritionist",
        "tell",
        "answer",
        (
            "Answer the current profile setup or onboarding question. Use this when "
            "the request contains both the question shown to the user and its answer."
        ),
        {
            "Username": {"type": "string", "source": "gateway"},
            "Field": {
                "type": "string",
                "enum": [
                    "height",
                    "weight",
                    "age",
                    "sex",
                    "activity",
                    "allergens",
                    "diet_type",
                    "culinary_preferences",
                ],
            },
            "Value": {"type": ["string", "number"]},
        },
        ["Username", "Field", "Value"],
    ),
    "nutritionist.build_week_plan": _message(
        "nutritionist",
        "tell",
        "build_week_plan",
        "Generate a new weekly meal plan for the current user.",
        {"Username": {"type": "string", "source": "gateway"}},
        ["Username"],
    ),
    "nutritionist.get_meal_logs": _message(
        "nutritionist",
        "achieve",
        "get_meal_logs",
        "Show the user's meal history.",
        {"Username": {"type": "string", "source": "gateway"}},
        ["Username"],
    ),
    "nutritionist.get_weight_logs": _message(
        "nutritionist",
        "achieve",
        "get_weight_logs",
        "Show the user's weight history.",
        {"Username": {"type": "string", "source": "gateway"}},
        ["Username"],
    ),
    "nutritionist.get_current_plan": _message(
        "nutritionist",
        "achieve",
        "get_current_plan",
        "Show the current day's meal plan.",
        {"Username": {"type": "string", "source": "gateway"}},
        ["Username"],
    ),
    "nutritionist.get_daily_recap": _message(
        "nutritionist",
        "achieve",
        "get_daily_recap",
        "Show today's calorie recap.",
        {"Username": {"type": "string", "source": "gateway"}},
        ["Username"],
    ),
    "nutritionist.update_weight": _message(
        "nutritionist",
        "tell",
        "update_weight",
        (
            "Update the weight in an already-completed profile. Rebuild the weekly "
            "plan when the change from the previous measurement is at least 1%; on "
            "reaching the target, switch to maintenance targets and rebuild. Do not "
            "use for an onboarding question reply."
        ),
        {
            "Username": {"type": "string", "source": "gateway"},
            "NewWeight": {"type": "number", "minimum": 0},
        },
        ["Username", "NewWeight"],
    ),
    "nutritionist.update_preferences": _message(
        "nutritionist",
        "tell",
        "update_preferences",
        (
            "Change the diet type in an already-completed profile and rebuild its "
            "weekly plan. Do not use for an onboarding question reply."
        ),
        {
            "Username": {"type": "string", "source": "gateway"},
            "DietType": {
                "type": "string",
                "enum": ["omnivore", "vegetarian", "vegan"],
            },
        },
        ["Username", "DietType"],
    ),
    "nutritionist.update_culinary_preferences": _message(
        "nutritionist",
        "tell",
        "update_culinary_preferences",
        (
            "Change culinary preferences in an already-completed profile. Do not "
            "use for an onboarding question reply."
        ),
        {
            "Username": {"type": "string", "source": "gateway"},
            "CulinaryPreferences": {"type": "string"},
        },
        ["Username", "CulinaryPreferences"],
    ),
    "nutritionist.confirm_meal": _message(
        "nutritionist",
        "tell",
        "confirm_meal",
        "Confirm that today's planned meal for a slot was eaten.",
        {
            "Username": {"type": "string", "source": "gateway"},
            "MealType": {"type": "string", "enum": _MEAL_SLOTS[:-1]},
        },
        ["Username", "MealType"],
    ),
    "nutritionist.log_meal": _message(
        "nutritionist",
        "tell",
        "log_meal",
        "Log a free-form meal for a slot. Calories may be a number or the string unknown.",
        {
            "Username": {"type": "string", "source": "gateway"},
            "Slot": {"type": "string", "enum": _MEAL_SLOTS},
            "Name": {"type": "string"},
            "Calories": {
                "anyOf": [
                    {"type": "number", "minimum": 0},
                    {"const": "unknown"},
                ]
            },
        },
        ["Username", "Slot", "Name", "Calories"],
    ),
    "planner.get_plan": _message(
        "planner",
        "achieve",
        "get_plan",
        "Show the user's weekly meal plan.",
        {"Username": {"type": "string", "source": "gateway"}},
        ["Username"],
    ),
}


def get_messages(ids: list[str]) -> list[Messages]:
    """Return complete definitions for known, unique message identifiers."""
    seen: set[str] = set()
    definitions: list[Messages] = []
    for message_id in ids:
        if message_id not in MESSAGES or message_id in seen:
            continue
        seen.add(message_id)
        definitions.append(deepcopy(MESSAGES[message_id]))
    return definitions


def get_message_signatures(functor: str | None = None) -> list[Messages]:
    """Return registry definitions, optionally filtered by ASL functor."""
    definitions = list(MESSAGES.values())
    if functor:
        definitions = [
            definition
            for definition in definitions
            if definition["name"] == functor.strip().lower()
        ]
    return deepcopy(definitions)
