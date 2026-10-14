from fastapi.testclient import TestClient

import main
from models.request_models import MarketResearchReport
from services.llm import LLMError

client = TestClient(main.app)


def test_research_without_context_returns_empty_report(monkeypatch):
    async def no_context(query):
        return []

    monkeypatch.setattr(main, "retrieve_context", no_context)
    response = client.post("/research", json={"query": "electric scooters"})
    assert response.status_code == 200
    assert response.json()["executive_summary"] == "No relevant context found."


def test_research_returns_generated_report(monkeypatch):
    async def some_context(query):
        return [{"text": "Acme sells scooters.", "metadata": {"url": "https://example.com"}}]

    async def fake_generate(query, chunks):
        return MarketResearchReport(
            industry_name="Micromobility",
            executive_summary="Growing.",
            key_trends=[],
            competitors=[],
            whitespace_opportunities=[],
        )

    monkeypatch.setattr(main, "retrieve_context", some_context)
    monkeypatch.setattr(main, "generate_research_report", fake_generate)
    response = client.post("/research", json={"query": "electric scooters"})
    assert response.status_code == 200
    assert response.json()["industry_name"] == "Micromobility"


def test_research_maps_llm_errors_to_502(monkeypatch):
    async def some_context(query):
        return [{"text": "Acme sells scooters.", "metadata": {}}]

    async def failing_generate(query, chunks):
        raise LLMError("The model declined to answer this query.")

    monkeypatch.setattr(main, "retrieve_context", some_context)
    monkeypatch.setattr(main, "generate_research_report", failing_generate)
    response = client.post("/research", json={"query": "electric scooters"})
    assert response.status_code == 502
    assert "declined" in response.json()["detail"]
