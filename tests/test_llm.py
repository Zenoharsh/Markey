import json
from types import SimpleNamespace

import httpx
import pytest

from config import get_settings
from models.request_models import ReportDraft as MarketResearchReport
from services import llm
from services.llm import AnthropicProvider, LLMError, OllamaProvider, get_llm_provider

VALID_REPORT = {
    "industry_name": "Note-taking apps",
    "executive_summary": "A crowded market.",
    "executive_summary_source_ids": [1],
    "key_figures": [
        {"label": "Market size", "value": 7.2, "unit": "USD billion", "year": 2025, "kind": "market_size", "source_ids": [1]}
    ],
    "key_trends": [{"text": "AI summaries", "source_ids": [1]}],
    "growth_drivers": [],
    "challenges": [],
    "customer_segments": [],
    "competitors": [
        {
            "name": "Acme Notes",
            "pricing_model": "Freemium",
            "core_value_proposition": "Fast capture",
            "target_audience": "Students",
            "scale": None,
            "market_share_percent": None,
            "source_ids": [1],
        }
    ],
    "competitive_forces": [],
    "whitespace_opportunities": [{"text": "Offline-first teams", "source_ids": [2]}],
    "recommendations": [],
    "data_gaps": [],
}


def mock_ollama(monkeypatch, responses):
    """Serves the given model outputs in order from a fake Ollama /api/generate."""
    calls = []
    outputs = iter(responses)

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"response": next(outputs)})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        llm.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    return calls


def test_default_provider_is_ollama():
    assert isinstance(get_llm_provider(), OllamaProvider)


def test_anthropic_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        get_llm_provider()


async def test_ollama_returns_validated_report(monkeypatch):
    calls = mock_ollama(monkeypatch, [json.dumps(VALID_REPORT)])
    report = await OllamaProvider(get_settings()).generate_structured("prompt", MarketResearchReport)
    assert report.competitors[0].name == "Acme Notes"
    assert calls[0]["model"] == "llama3.2"
    assert calls[0]["format"]["required"] == MarketResearchReport.model_json_schema()["required"]
    assert calls[0]["options"]["num_ctx"] == 16384


async def test_ollama_retries_once_on_invalid_json(monkeypatch):
    calls = mock_ollama(monkeypatch, ["not json", json.dumps(VALID_REPORT)])
    report = await OllamaProvider(get_settings()).generate_structured("prompt", MarketResearchReport)
    assert report.industry_name == "Note-taking apps"
    assert len(calls) == 2


async def test_ollama_raises_after_two_invalid_outputs(monkeypatch):
    mock_ollama(monkeypatch, ["not json", json.dumps({"industry_name": "missing fields"})])
    with pytest.raises(LLMError, match="expected format"):
        await OllamaProvider(get_settings()).generate_structured("prompt", MarketResearchReport)


class FakeParse:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def anthropic_provider(monkeypatch, model, response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", model)
    provider = AnthropicProvider(get_settings())
    standard, beta = FakeParse(response), FakeParse(response)
    provider.client = SimpleNamespace(messages=standard, beta=SimpleNamespace(messages=beta))
    return provider, standard, beta


async def test_anthropic_sonnet_uses_server_side_fallback(monkeypatch):
    report = MarketResearchReport.model_validate(VALID_REPORT)
    response = SimpleNamespace(stop_reason="end_turn", parsed_output=report)
    provider, standard, beta = anthropic_provider(monkeypatch, "claude-sonnet-5-5", response)

    assert await provider.generate_structured("prompt", MarketResearchReport) == report
    assert standard.kwargs is None
    assert beta.kwargs["fallbacks"] == "default"
    assert beta.kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert beta.kwargs["output_format"] is MarketResearchReport


async def test_anthropic_haiku_skips_fallback(monkeypatch):
    report = MarketResearchReport.model_validate(VALID_REPORT)
    response = SimpleNamespace(stop_reason="end_turn", parsed_output=report)
    provider, standard, beta = anthropic_provider(monkeypatch, "claude-haiku-5-5", response)

    await provider.generate_structured("prompt", MarketResearchReport)
    assert beta.kwargs is None
    assert "fallbacks" not in standard.kwargs


@pytest.mark.parametrize(
    "stop_reason, message",
    [("refusal", "declined"), ("max_tokens", "ran out of output tokens")],
)
async def test_anthropic_unusable_stop_reasons_raise(monkeypatch, stop_reason, message):
    response = SimpleNamespace(stop_reason=stop_reason, parsed_output=None)
    provider, _, _ = anthropic_provider(monkeypatch, "claude-sonnet-5-5", response)
    with pytest.raises(LLMError, match=message):
        await provider.generate_structured("prompt", MarketResearchReport)


def mock_gemini(monkeypatch, status, body):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        llm.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    return calls


def gemini_answer(text, finish="STOP"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}]}


def gemini_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return get_llm_provider()


async def test_gemini_returns_validated_report(monkeypatch):
    calls = mock_gemini(monkeypatch, 200, gemini_answer(json.dumps(VALID_REPORT)))
    report = await gemini_provider(monkeypatch).generate_structured("prompt", MarketResearchReport)

    assert report.competitors[0].name == "Acme Notes"
    request = calls[0]
    assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
    assert request.headers["x-goog-api-key"] == "test-key"
    schema = json.loads(request.content)["generationConfig"]["responseJsonSchema"]
    # References are inlined, so nested objects are spelled out
    assert "$defs" not in json.dumps(schema)
    assert schema["properties"]["key_trends"]["items"]["properties"]["text"]["type"] == "string"


def test_gemini_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        get_llm_provider()


@pytest.mark.parametrize(
    "status, body, message",
    [
        (429, {"error": {"message": "quota"}}, "rate limit"),
        (400, {"error": {"message": "API key not valid"}}, "API key not valid"),
        (200, {"promptFeedback": {"blockReason": "SAFETY"}}, "declined"),
        (200, gemini_answer("{}", finish="MAX_TOKENS"), "ran out of output tokens"),
        (200, gemini_answer("not json"), "expected format"),
    ],
)
async def test_gemini_failures_raise_llm_error(monkeypatch, status, body, message):
    mock_gemini(monkeypatch, status, body)
    with pytest.raises(LLMError, match=message):
        await gemini_provider(monkeypatch).generate_structured("prompt", MarketResearchReport)
