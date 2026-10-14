import json

from fastapi.testclient import TestClient

import main
from models.request_models import MarketResearchReport
from services.llm import LLMError
from services.research import InsufficientEvidence

client = TestClient(main.app)

REPORT = MarketResearchReport(
    industry_name="Micromobility",
    executive_summary="Growing.",
    executive_summary_source_ids=[1],
    key_trends=[],
    competitors=[],
    whitespace_opportunities=[],
    sources=[{"id": 1, "url": "https://a.example", "title": "A", "retrieved_at": ""}],
)


def fake_research(result=None, error=None):
    async def run(topic, progress=None):
        if progress:
            await progress("searching", f"Searching the web for {topic!r}")
        if error:
            raise error
        return result

    return run


def test_research_returns_cited_report(monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    response = client.post("/research", json={"query": "electric scooters"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["url"] == "https://a.example"


def test_research_maps_errors_to_statuses(monkeypatch):
    cases = [
        (InsufficientEvidence("Only 1 usable sources"), 422, "Only 1"),
        (LLMError("The model declined to answer this query."), 502, "declined"),
        (RuntimeError("secret internals"), 500, "Something went wrong"),
    ]
    for error, status, detail in cases:
        monkeypatch.setattr(main, "run_research", fake_research(error=error))
        response = client.post("/research", json={"query": "electric scooters"})
        assert response.status_code == status
        assert detail in response.json()["detail"]


def test_research_rejects_empty_query():
    assert client.post("/research", json={"query": ""}).status_code == 422


def stream_events(query):
    response = client.post("/research/stream", json={"query": query})
    assert response.headers["content-type"].startswith("text/event-stream")
    return [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_stream_sends_progress_then_report(monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    events = stream_events("electric scooters")
    assert [e["type"] for e in events] == ["progress", "report"]
    assert events[1]["report"]["industry_name"] == "Micromobility"


def test_stream_sends_error_event(monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(error=InsufficientEvidence("Only 0 usable sources")))
    events = stream_events("electric scooters")
    assert events[-1] == {"type": "error", "status": 422, "detail": "Only 0 usable sources"}
