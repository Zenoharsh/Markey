import json
from types import SimpleNamespace

import httpx
import pytest

from config import get_settings
from models.request_models import MarketResearchReport
from services import llm
from services.llm import AnthropicProvider, LLMError, OllamaProvider, get_llm_provider

VALID_REPORT = {
    "industry_name": "Note-taking apps",
    "executive_summary": "A crowded market.",
    "key_trends": ["AI summaries"],
    "competitors": [
        {
            "name": "Acme Notes",
            "pricing_model": "Freemium",
            "core_value_proposition": "Fast capture",
            "target_audience": "Students",
            "market_strength_score": 6,
        }
    ],
    "whitespace_opportunities": ["Offline-first teams"],
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
    assert calls[0]["format"] == "json"


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
