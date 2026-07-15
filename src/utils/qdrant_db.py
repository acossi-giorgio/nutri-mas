from __future__ import annotations

import uuid
from typing import Any, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.domain.constants import ONBOARDING_QUESTIONS
from src.utils.embedding_config import embed_texts, embedding_model_name
from src.utils.logger import get_logger
from src.utils.messages_registry import get_message_signatures

logger = get_logger("QdrantDB")
_COLLECTION_NAME = "nlp_translations"
_qdrant_client = QdrantClient(location=":memory:")


class TranslationTemplate(TypedDict):
    """One language example linked to a registered message."""

    nl_template: str
    message: str


ONBOARDING_TEMPLATES: list[TranslationTemplate] = [
    {
        "nl_template": f"Question: {question}\nAnswer: {{{field}}}",
        "message": "nutritionist.answer",
    }
    for field, question in ONBOARDING_QUESTIONS.items()
]


DEFAULT_TEMPLATES: list[TranslationTemplate] = [
    *ONBOARDING_TEMPLATES,
    {
        "nl_template": "Generate a new weekly meal plan.",
        "message": "nutritionist.build_week_plan",
    },
    {
        "nl_template": "Build a new meal plan for me.",
        "message": "nutritionist.build_week_plan",
    },
    {
        "nl_template": "Show me my meal history.",
        "message": "nutritionist.get_meal_logs",
    },
    {
        "nl_template": "Show me my weight history.",
        "message": "nutritionist.get_weight_logs",
    },
    {
        "nl_template": "What should I eat today?",
        "message": "nutritionist.get_current_plan",
    },
    {
        "nl_template": "Show me today's meal plan.",
        "message": "nutritionist.get_current_plan",
    },
    {
        "nl_template": "Show me today's nutrition summary.",
        "message": "nutritionist.get_daily_recap",
    },
    {
        "nl_template": "What have I eaten today?",
        "message": "nutritionist.get_daily_recap",
    },
    {
        "nl_template": "In my existing profile, change my current weight to {weight} kg.",
        "message": "nutritionist.update_weight",
    },
    {
        "nl_template": "In my existing profile, change my diet preference to {diet_type}.",
        "message": "nutritionist.update_preferences",
    },
    {
        "nl_template": (
            "I want to replace the diet preference in my existing profile with "
            "{diet_type}."
        ),
        "message": "nutritionist.update_preferences",
    },
    {
        "nl_template": (
            "My profile is already complete; change my culinary preferences to "
            "{preferences}."
        ),
        "message": "nutritionist.update_culinary_preferences",
    },
    {
        "nl_template": (
            "In my existing profile, change my recipe preferences to {preferences}."
        ),
        "message": "nutritionist.update_culinary_preferences",
    },
    {
        "nl_template": (
            "Question: Did you eat the planned {meal_type}: {planned_recipe}?\n"
            "Answer: Yes, I ate it."
        ),
        "message": "nutritionist.confirm_meal",
    },
    {
        "nl_template": (
            "Question: Did you eat the planned {meal_type}: {planned_recipe}?\n"
            "Answer: Yes."
        ),
        "message": "nutritionist.confirm_meal",
    },
    {
        "nl_template": (
            "Question: Did you eat the planned {meal_type}: {planned_recipe}?\n"
            "Answer: No, I ate {actual_food} instead."
        ),
        "message": "nutritionist.log_meal",
    },
    {
        "nl_template": (
            "Question: Did you eat the planned {meal_type}: {planned_recipe}?\n"
            "Answer: Yes, but I ate {actual_food} instead."
        ),
        "message": "nutritionist.log_meal",
    },
    {
        "nl_template": "I ate {actual_food} for {meal_type}.",
        "message": "nutritionist.log_meal",
    },
    {
        "nl_template": "I had {actual_food} for {meal_type}, about {calories} kcal.",
        "message": "nutritionist.log_meal",
    },
    {
        "nl_template": "Show me my weekly meal plan.",
        "message": "planner.get_plan",
    },
    {
        "nl_template": "What is my plan for the week?",
        "message": "planner.get_plan",
    },
]


def init_qdrant() -> None:
    """Rebuild Qdrant from the minimal English template registry."""
    try:
        texts = [template["nl_template"] for template in DEFAULT_TEMPLATES]
        vectors = embed_texts(texts)
        vector_size = len(vectors[0])
        if _qdrant_client.collection_exists(_COLLECTION_NAME):
            _qdrant_client.delete_collection(_COLLECTION_NAME)
        logger.info(
            "Creating Qdrant collection: %s model=%s dimensions=%d",
            _COLLECTION_NAME,
            embedding_model_name(),
            vector_size,
        )
        _qdrant_client.create_collection(
            collection_name=_COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=dict(template),
            )
            for template, vector in zip(DEFAULT_TEMPLATES, vectors)
        ]
        _qdrant_client.upsert(collection_name=_COLLECTION_NAME, points=points)
        logger.info("Qdrant collection populated with %d templates.", len(points))
    except Exception as exc:
        logger.error("Failed to initialize Qdrant: %s", exc)


def search_message_templates(query: str, limit: int = 5) -> list[str]:
    """Return the best distinct message IDs for a language query."""
    try:
        query_vector = embed_texts([query])[0]
        results = _qdrant_client.query_points(
            collection_name=_COLLECTION_NAME,
            query=query_vector,
            limit=max(limit * 4, 20),
        )
        candidates: list[str] = []
        seen: set[str] = set()
        for point in results.points:
            payload = point.payload or {}
            message_id = str(payload.get("message", "")).strip()
            if not message_id or message_id in seen:
                continue
            seen.add(message_id)
            candidates.append(message_id)
            if len(candidates) == limit:
                break
        logger.info("NLP message search: query=%s results=%s", query, candidates)
        return candidates
    except Exception as exc:
        logger.error("Qdrant search error: %s", exc)
        return []


def get_translation_signatures(bdi_functor: str | None = None) -> list[dict[str, Any]]:
    """Return compatibility command signatures from the message registry."""
    definitions = get_message_signatures(bdi_functor)
    payload = [
        {
            "prolog_template": definition["signature"],
            "bdi_functor": definition["name"],
            "target_agent": definition["agent"],
            "performative": definition["message_performative"],
        }
        for definition in definitions
    ]
    logger.info("NLP signature lookup: functor=%s results=%s", bdi_functor, payload)
    return payload
