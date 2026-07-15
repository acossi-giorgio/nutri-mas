from __future__ import annotations

import asyncio
import csv
import json
import os
import uuid
from pathlib import Path
from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.utils.embedding_config import embed_texts, embedding_model_name
from src.utils.logger import get_logger

logger = get_logger("IngredientStore")
_COLLECTION = "ingredients"
_CACHE_VERSION = 1


def _embedding_timeout_seconds() -> float:
    """Return the configured embedding timeout."""
    return float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))


def _embedding_batch_size() -> int:
    """Return the configured embedding batch size."""
    return int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))


def _embedding_cache_path() -> Path:
    """Return the configured embedding cache path."""
    return Path(
        os.getenv(
            "INGREDIENT_EMBEDDINGS_CACHE_PATH",
            ".cache/ingredient_embeddings.json",
        )
    )


def _embedding_model_name() -> str:
    """Return the configured embedding model name used as a cache key."""
    return embedding_model_name()


def _litellm_embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via LiteLLM."""
    return embed_texts(texts)


def _row_to_text(row: dict[str, str]) -> str:
    """Build the text to embed for semantic ingredient search."""
    return row.get("ingredient", "Unknown ingredient")


def _load_embedding_cache() -> dict[str, list[float]]:
    """Read cached ingredient embeddings from a local, git-ignored JSON file."""
    cache_path = _embedding_cache_path()
    if not cache_path.exists():
        return {}
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        logger.exception(
            "Ignoring unreadable ingredient embedding cache: %s", cache_path
        )
        return {}
    if payload.get("version") != _CACHE_VERSION:
        logger.info(
            "Ignoring ingredient embedding cache with unsupported version: %s",
            cache_path,
        )
        return {}
    if payload.get("model") != _embedding_model_name():
        logger.info(
            "Ignoring ingredient embedding cache for different model: %s", cache_path
        )
        return {}
    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, dict):
        logger.info(
            "Ignoring ingredient embedding cache with invalid payload: %s", cache_path
        )
        return {}
    valid: dict[str, list[float]] = {}
    for key, value in embeddings.items():
        if (
            isinstance(key, str)
            and isinstance(value, list)
            and value
            and all(isinstance(item, int | float) for item in value)
        ):
            valid[key] = value
    logger.info(
        "Loaded %d cached ingredient embeddings from %s", len(valid), cache_path
    )
    return valid


def _save_embedding_cache(cache: dict[str, list[float]]) -> None:
    """Persist ingredient embeddings atomically for faster future startups."""
    cache_path = _embedding_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    payload = {
        "version": _CACHE_VERSION,
        "model": _embedding_model_name(),
        "embeddings": cache,
    }
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=True)
        os.replace(tmp_path, cache_path)
        logger.info(
            "Saved %d ingredient embeddings to cache: %s", len(cache), cache_path
        )
    except OSError:
        logger.exception("Could not write ingredient embedding cache: %s", cache_path)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


class QdrantIngredientStore:
    """Holds a Qdrant in-memory collection of ingredient vectors."""

    def __init__(self) -> None:
        """Initialize the instance."""
        self._client: QdrantClient | None = None
        self._ready = False
        self._semantic_ready = False

    async def build_from_csv(self, csv_path: str) -> None:
        """Load ingredients from CSV and build the semantic Qdrant collection."""
        rows: list[dict[str, str]] = []
        with open(csv_path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("ingredient"):
                    rows.append(row)
        if not rows:
            raise RuntimeError(f"Ingredient CSV is empty or invalid: {csv_path}")
        logger.info("Loaded ingredient store from %d CSV rows.", len(rows))
        texts = [_row_to_text(r) for r in rows]
        await self._build_embeddings(rows, texts)
        self._ready = True

    async def _build_embeddings(
        self, rows: list[dict[str, str]], texts: list[str]
    ) -> None:
        """Build the semantic vector index for ingredient search."""
        logger.info(
            "Building Qdrant ingredient store from %d rows using embeddings.", len(rows)
        )
        cache = _load_embedding_cache()
        missing_texts = [text for text in dict.fromkeys(texts) if text not in cache]
        batch_size = max(1, _embedding_batch_size())
        if missing_texts:
            logger.info(
                "Ingredient embedding cache missing %d/%d unique texts.",
                len(missing_texts),
                len(dict.fromkeys(texts)),
            )
            for i in range(0, len(missing_texts), batch_size):
                batch_texts = missing_texts[i : i + batch_size]
                logger.info(
                    "Embedding ingredient cache batch %d-%d/%d...",
                    i + 1,
                    min(i + batch_size, len(missing_texts)),
                    len(missing_texts),
                )
                embeddings = await asyncio.wait_for(
                    asyncio.to_thread(_litellm_embed, batch_texts),
                    timeout=_embedding_timeout_seconds() + 5,
                )
                if len(embeddings) != len(batch_texts):
                    raise RuntimeError(
                        "LiteLLM returned "
                        f"{len(embeddings)} embeddings for {len(batch_texts)} ingredients."
                    )
                cache.update(dict(zip(batch_texts, embeddings)))
            _save_embedding_cache(cache)
        else:
            logger.info(
                "Ingredient embedding cache hit for all %d unique texts.",
                len(dict.fromkeys(texts)),
            )
        all_embeddings = [cache[text] for text in texts]
        if len(all_embeddings) != len(rows):
            raise RuntimeError(
                f"Built {len(all_embeddings)} embeddings for {len(rows)} ingredient rows."
            )
        if not all_embeddings or not all_embeddings[0]:
            raise RuntimeError("LiteLLM returned empty ingredient embeddings.")
        vector_size = len(all_embeddings[0])
        if any(len(vector) != vector_size for vector in all_embeddings):
            raise RuntimeError(
                "Ingredient embedding cache contains vectors with inconsistent dimensions. "
                f"Delete {_embedding_cache_path()} and restart."
            )
        client = QdrantClient(":memory:")
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "ingredient": row.get("ingredient", ""),
                    "calories": row.get("calories", "0"),
                    "protein_g": row.get("protein_g", "0"),
                    "carbs_g": row.get("carbs_g", "0"),
                    "fat_g": row.get("fat_g", "0"),
                },
            )
            for row, vector in zip(rows, all_embeddings)
        ]
        client.upsert(collection_name=_COLLECTION, points=points)
        self._client = client
        self._semantic_ready = True
        logger.info("Qdrant ingredient semantic store ready (%d vectors).", len(rows))

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top-k semantic matches from the ingredient collection."""
        if not self._ready:
            raise RuntimeError("Ingredient store is not ready.")
        if self._client is None or not self._semantic_ready:
            raise RuntimeError("Ingredient semantic search is not available.")
        logger.info(
            "Ingredient semantic search started: query=%s limit=%s", query, limit
        )
        query_embeddings = _litellm_embed([query])
        query_vector = query_embeddings[0]
        results = self._client.query_points(
            collection_name=_COLLECTION,
            query=query_vector,
            limit=max(1, limit),
        )
        filtered: list[dict[str, Any]] = []
        for hit in results.points:
            payload = hit.payload if hit.payload else {}
            filtered.append(
                {
                    "ingredient": payload.get("ingredient", ""),
                    "calories": payload.get("calories", "0"),
                    "protein_g": payload.get("protein_g", "0"),
                    "carbs_g": payload.get("carbs_g", "0"),
                    "fat_g": payload.get("fat_g", "0"),
                }
            )
        logger.debug("Ingredient search '%s' → %d results", query, len(filtered))
        logger.info(
            "Ingredient semantic search completed: query=%s results=%d",
            query,
            len(filtered),
        )
        return filtered

    @property
    def is_ready(self) -> bool:
        """True if the CSV-backed ingredient store was built successfully."""
        return self._ready

    @property
    def is_semantic_ready(self) -> bool:
        """True if the optional vector index was built successfully."""
        return self._semantic_ready
