import json
import logging
from functools import lru_cache
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Server-side refusal fallbacks are not offered for Haiku models
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """The language model could not produce a usable answer."""


class LLMProvider(Protocol):
    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        """Returns the model's answer to `prompt`, validated against `schema`."""
        ...


class OllamaProvider:
    def __init__(self, settings: Settings):
        self.url = f"{settings.ollama_base_url}/api/generate"
        self.model = settings.ollama_chat_model
        self.timeout = settings.llm_timeout_seconds
        self.num_ctx = settings.ollama_num_ctx

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        payload = {
            "model": self.model,
            "prompt": prompt,
            # Constraining output to the schema stops small models replying with {} or partial objects
            "format": schema.model_json_schema(),
            "stream": False,
            # Ollama's default context is too small for the source passages and silently cuts the prompt
            "options": {"num_ctx": self.num_ctx},
        }
        # Small local models sometimes return malformed JSON, so allow one retry
        last_error: Exception | None = None
        for attempt in range(2):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, json=payload)
                response.raise_for_status()
                text = response.json().get("response", "{}")
            try:
                return schema.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Ollama returned invalid output (attempt {attempt + 1}): {e}")
                last_error = e
        raise LLMError(f"Model output did not match the expected format: {last_error}")


class AnthropicProvider:
    def __init__(self, settings: Settings):
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic")
        # Imported here so the Ollama-only setup does not need the SDK at import time
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
        )
        self.model = settings.anthropic_model

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        try:
            response = await self._parse(prompt, schema)
        except self._anthropic.APITimeoutError as e:
            raise LLMError("The model timed out generating the report.") from e
        except self._anthropic.APIError as e:
            raise LLMError(f"The Claude API returned an error: {e}") from e

        if response.stop_reason == "refusal":
            raise LLMError("The model declined to answer this query.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The model ran out of output tokens before finishing the report.")
        if response.parsed_output is None:
            raise LLMError("The model did not return a structured report.")
        return response.parsed_output

    async def _parse(self, prompt: str, schema: type[T]):
        messages = [{"role": "user", "content": prompt}]
        if self.model.startswith("claude-haiku"):
            return await self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                messages=messages,
                output_format=schema,
            )
        # On a safety decline, the API re-runs the request on a recommended fallback model
        return await self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            betas=[_FALLBACK_BETA],
            fallbacks="default",
            messages=messages,
            output_format=schema,
        )


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings)
    return OllamaProvider(settings)
