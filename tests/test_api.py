import json

import pytest
from fastapi.testclient import TestClient

import main
from models.request_models import MarketResearchReport
from services.llm import LLMError
from services.research import InsufficientEvidence

from services import store


@pytest.fixture
def client():
    # One event loop for the whole test, so background jobs outlive the request that started them
    with TestClient(main.app) as test_client:
        yield test_client

REPORT = MarketResearchReport(
    industry_name="Micromobility",
    executive_summary="Growing.",
    executive_summary_source_ids=[1],
    key_figures=[],
    key_trends=[],
    growth_drivers=[],
    challenges=[],
    customer_segments=[],
    competitors=[],
    competitive_forces=[],
    whitespace_opportunities=[],
    recommendations=[],
    data_gaps=[],
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


def test_research_returns_cited_report(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    response = client.post("/research", json={"query": "electric scooters"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["url"] == "https://a.example"


def test_research_maps_errors_to_statuses(client, monkeypatch):
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


def test_research_rejects_empty_query(client):
    assert client.post("/research", json={"query": ""}).status_code == 422


def stream_events(client, query):
    response = client.post("/research/stream", json={"query": query})
    assert response.headers["content-type"].startswith("text/event-stream")
    return [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_stream_sends_progress_then_report(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    events = stream_events(client, "electric scooters")
    assert [e["type"] for e in events] == ["job", "progress", "report"]
    assert events[2]["report"]["industry_name"] == "Micromobility"


def test_stream_sends_error_event(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(error=InsufficientEvidence("Only 0 usable sources")))
    events = stream_events(client, "electric scooters")
    assert events[-1] == {"type": "error", "status": 422, "detail": "Only 0 usable sources"}


def parse_events(response):
    return [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_stream_starts_with_job_id_and_saves_report(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    events = stream_events(client, "electric scooters")
    job_id = events[0]["id"]
    assert events[0]["type"] == "job"

    history = client.get("/reports").json()
    assert [(r["id"], r["status"], r["industry_name"], r["source_count"]) for r in history] == [
        (job_id, "done", "Micromobility", 1)
    ]
    saved = client.get(f"/reports/{job_id}").json()
    assert saved["report"]["executive_summary"] == "Growing."


def test_job_events_replay_for_a_late_client(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    job_id = client.post("/research/jobs", json={"query": "electric scooters"}).json()["id"]
    events = parse_events(client.get(f"/research/jobs/{job_id}/events"))
    assert [e["type"] for e in events] == ["job", "progress", "report"]
    # Connecting again after it finished still delivers the result
    again = parse_events(client.get(f"/research/jobs/{job_id}/events"))
    assert again[-1]["report"]["industry_name"] == "Micromobility"


def test_failed_runs_are_saved_with_their_reason(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(error=InsufficientEvidence("Only 0 usable sources")))
    job_id = stream_events(client, "electric scooters")[0]["id"]
    saved = client.get(f"/reports/{job_id}").json()
    assert (saved["status"], saved["error_status"], saved["error"]) == ("failed", 422, "Only 0 usable sources")


def test_stored_run_is_replayed_after_restart(client):
    run_id = store.create_run("solar panels")
    store.finish_run(run_id, REPORT, 12.3)
    events = parse_events(client.get(f"/research/jobs/{run_id}/events"))
    assert events[-1]["type"] == "report"


def test_restart_marks_unfinished_runs_interrupted(client):
    run_id = store.create_run("solar panels")
    with TestClient(main.app):
        pass
    assert store.get_run(run_id)["status"] == "failed"


def test_unknown_job_and_report_return_404(client):
    assert client.get("/research/jobs/nope/events").status_code == 404
    assert client.get("/reports/nope").status_code == 404
    assert client.delete("/reports/nope").status_code == 404


def test_delete_report(client, monkeypatch):
    monkeypatch.setattr(main, "run_research", fake_research(REPORT))
    job_id = stream_events(client, "electric scooters")[0]["id"]
    assert client.delete(f"/reports/{job_id}").status_code == 204
    assert client.get("/reports").json() == []
