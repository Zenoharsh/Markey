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


def _inline_refs(schema: dict) -> dict:
    """Replaces $ref pointers with the definitions they name, for APIs that don't follow them."""
    defs = schema.get("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


class GeminiProvider:
    """Google's Gemini API, which has a free tier. Output is constrained to the report schema."""

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY must be set when LLM_PROVIDER=gemini")
        self.api_key = settings.gemini_api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
        self.timeout = settings.llm_timeout_seconds

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _inline_refs(schema.model_json_schema()),
                "temperature": 0.2,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, json=payload, headers={"x-goog-api-key": self.api_key})
        except httpx.TimeoutException as e:
            raise LLMError("Gemini timed out generating the report.") from e
        if response.status_code == 429:
            raise LLMError("Gemini's rate limit was reached. Wait a minute and try again.")
        if response.status_code >= 400:
            message = response.json().get("error", {}).get("message", response.text[:200]) if response.content else ""
            raise LLMError(f"The Gemini API returned an error ({response.status_code}): {message}")

        data = response.json()
        if block := data.get("promptFeedback", {}).get("blockReason"):
            raise LLMError(f"Gemini declined to answer this query ({block}).")
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("Gemini returned no answer.")
        finish = candidates[0].get("finishReason")
        if finish == "MAX_TOKENS":
            raise LLMError("The model ran out of output tokens before finishing the report.")
        if finish not in (None, "STOP"):
            raise LLMError(f"Gemini stopped before finishing the report ({finish}).")
        text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
        try:
            return schema.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as e:
            raise LLMError(f"Model output did not match the expected format: {e}") from e


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings)
    if settings.llm_provider == "gemini":
        return GeminiProvider(settings)
    return OllamaProvider(settings)
