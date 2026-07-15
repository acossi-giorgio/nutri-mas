from __future__ import annotations
import json
import os
import time
from typing import Any
import litellm
from spade_llm import LLMProvider
from src.utils.logger import get_logger

logger = get_logger("LLMProvider")

_DEFAULT_LLM_TIMEOUT_SECONDS = 60.0
_DEFAULT_LLM_NUM_RETRIES = 2


def _normalize_loopback_url(url: str) -> str:
    """Avoid Windows localhost resolving to IPv6 when the proxy binds IPv4 only."""
    return url.replace("://localhost", "://127.0.0.1", 1)


class ProxyLLMProvider(LLMProvider):
    """LiteLLM provider patched for current OpenAI structured output clients."""

    @staticmethod
    def _response_format_for_schema(output_schema: Any) -> dict[str, Any]:
        """Build the structured-output response format."""
        schema_method = getattr(output_schema, "model_json_schema", None)
        if callable(schema_method):
            schema = schema_method()
        else:
            schema = output_schema.schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": output_schema.__name__,
                "schema": schema,
                "strict": False,
            },
        }

    async def get_llm_response(
        self,
        context: Any,
        tools: list[Any] | None = None,
        conversation_id: str | None = None,
        output_schema: Any | None = None,
    ) -> dict[str, Any]:
        """Request and normalize an LLM response."""
        prompt = context.get_prompt(conversation_id)
        formatted_tools = None
        if tools:
            formatted_tools = [tool.to_openai_tool() for tool in tools]
        try:
            completion_kwargs = self._build_completion_kwargs(
                context, prompt, formatted_tools
            )
            use_structured_output = output_schema is not None and not formatted_tools
            if use_structured_output:
                completion_kwargs["response_format"] = self._response_format_for_schema(
                    output_schema
                )
            started = time.perf_counter()
            logger.info(
                "LLM request started: model=%s conversation=%s prompt_chars=%s tools=%s structured_schema=%s",
                getattr(self, "model", "llm"),
                conversation_id,
                len(prompt or ""),
                [tool.name for tool in tools] if tools else [],
                getattr(output_schema, "__name__", None),
            )
            response = await litellm.acompletion(**completion_kwargs)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            message = response.choices[0].message
            result = {"tool_calls": [], "text": None, "structured": None}
            if use_structured_output:
                content = message.content or ""
                if content:
                    try:
                        result["structured"] = output_schema(**json.loads(content))
                    except Exception as exc:
                        logger.warning(
                            "Failed to parse structured output from content: %s", exc
                        )
                        result["text"] = content
                else:
                    result["text"] = content
                logger.info(
                    "LLM structured response completed: model=%s elapsed_ms=%s structured=%s text=%s",
                    getattr(self, "model", "llm"),
                    elapsed_ms,
                    (
                        result["structured"].model_dump()
                        if result["structured"] is not None
                        else None
                    ),
                    result["text"],
                )
                return result
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = []
                for tool_call in message.tool_calls:
                    try:
                        arguments = tool_call.function.arguments
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    tool_calls.append(
                        {
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "arguments": arguments,
                        }
                    )
                result["tool_calls"] = tool_calls
            else:
                result["text"] = message.content or ""
            logger.info(
                "LLM response completed: model=%s elapsed_ms=%s tool_calls=%s text=%s",
                getattr(self, "model", "llm"),
                elapsed_ms,
                result["tool_calls"],
                result["text"],
            )
            return result
        except Exception:
            logger.exception("LLM completion error")
            raise


def build_llm_provider() -> LLMProvider:
    """Build a SPADE-LLM provider backed by LiteLLM Proxy."""
    model_alias = os.getenv("LLM_MODEL").strip()
    if not model_alias.startswith("openai/"):
        model_alias = f"openai/{model_alias}"
    api_key = os.getenv("LITELLM_PROXY_API_KEY").strip()
    base_url = os.getenv("LITELLM_PROXY_BASE_URL").strip()
    base_url = _normalize_loopback_url(base_url)
    max_tokens_raw = os.getenv("LLM_MAX_TOKENS")
    num_retries_raw = os.getenv("LLM_NUM_RETRIES")
    temperature_raw = os.getenv("LLM_TEMPERATURE")
    timeout_raw = os.getenv("LLM_TIMEOUT")
    return ProxyLLMProvider(
        model=model_alias,
        api_key=api_key,
        base_url=base_url,
        temperature=float(temperature_raw) if temperature_raw else 1.0,
        timeout=(float(timeout_raw) if timeout_raw else _DEFAULT_LLM_TIMEOUT_SECONDS),
        max_tokens=int(max_tokens_raw) if max_tokens_raw else None,
        num_retries=(
            int(num_retries_raw) if num_retries_raw else _DEFAULT_LLM_NUM_RETRIES
        ),
    )
