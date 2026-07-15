from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import litellm
import yaml

from src.utils.llm_config import _normalize_loopback_url

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_GATEWAY_CONFIG = _PROJECT_ROOT / "config" / "litellm_config.yaml"


def _gateway_config_path() -> Path:
    """Return the LiteLLM gateway config path."""
    configured_path = os.getenv("LITELLM_CONFIG_PATH", "").strip()
    return Path(configured_path) if configured_path else _DEFAULT_GATEWAY_CONFIG


def _model_from_gateway_config(path: Path) -> str | None:
    """Find the embedding alias declared in a LiteLLM gateway config."""
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    model_list = config.get("model_list", [])
    if not isinstance(model_list, list):
        return None
    for entry in model_list:
        if not isinstance(entry, dict):
            continue
        alias = str(entry.get("model_name", "")).strip()
        params = entry.get("litellm_params", {})
        provider_model = (
            str(params.get("model", "")).strip() if isinstance(params, dict) else ""
        )
        mode = str(entry.get("mode", "")).strip().lower()
        if alias and (
            mode == "embedding"
            or "embedding" in alias.lower()
            or "embedding" in provider_model.lower()
        ):
            return alias
    return None


def embedding_model_name() -> str:
    """Return the gateway embedding alias, with `.env` as fallback only."""
    config_model = _model_from_gateway_config(_gateway_config_path())
    if config_model:
        return config_model
    env_model = os.getenv("EMBEDDING_MODEL", "").strip()
    if env_model:
        return env_model
    raise RuntimeError(
        "No embedding model is configured. Add an embedding model to "
        "config/litellm_config.yaml or set EMBEDDING_MODEL."
    )


def embedding_kwargs() -> dict[str, Any]:
    """Build LiteLLM arguments for the OpenAI-compatible gateway endpoint."""
    alias = embedding_model_name()
    proxy_model = alias if alias.startswith("openai/") else f"openai/{alias}"
    api_key = os.getenv("LITELLM_PROXY_API_KEY", "sk-local-dev").strip()
    api_base = os.getenv("LITELLM_PROXY_BASE_URL", "http://localhost:4000").strip()
    return {
        "model": proxy_model,
        "api_key": api_key,
        "api_base": _normalize_loopback_url(api_base),
    }


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text through the model alias exposed by the LiteLLM gateway."""
    if not texts:
        return []
    timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))
    response = litellm.embedding(
        input=texts,
        encoding_format="float",
        timeout=timeout,
        **embedding_kwargs(),
    )
    embeddings = [item["embedding"] for item in response.data]
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"LiteLLM returned {len(embeddings)} embeddings for {len(texts)} texts."
        )
    if not embeddings or not embeddings[0]:
        raise RuntimeError("LiteLLM returned empty embeddings.")
    vector_size = len(embeddings[0])
    if any(len(vector) != vector_size for vector in embeddings):
        raise RuntimeError("LiteLLM returned embeddings with inconsistent dimensions.")
    return embeddings
