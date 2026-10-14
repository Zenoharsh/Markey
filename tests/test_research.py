import pytest

from models.request_models import CitedText, CompetitorData, ReportDraft, Source
from services import research
from services.research import InsufficientEvidence, apply_citations, discover_sources, run_research
from services.search import SearchResult

LONG_TEXT = "Scooter sharing keeps growing in cities. " * 30


def source(i):
    return Source(id=i, url=f"https://s{i}.example", title=f"S{i}", retrieved_at="2026-10-14T00:00:00+00:00")


def competitor(name, ids):
    return CompetitorData(
        name=name, pricing_model="Per minute", core_value_proposition="Fast", target_audience="Commuters",
        market_strength_score=5, source_ids=ids,
    )


def draft(**overrides):
    values = dict(
        industry_name="Micromobility",
        executive_summary="Growing.",
        executive_summary_source_ids=[1, 9],
        key_trends=[CitedText(text="Supported", source_ids=[2, 2, 1]), CitedText(text="Made up", source_ids=[])],
        competitors=[competitor("Lime", [1]), competitor("Ghost Co", [7])],
        whitespace_opportunities=[CitedText(text="Bad citation", source_ids=[42])],
    )
    values.update(overrides)
    return ReportDraft(**values)


def test_apply_citations_drops_unsupported_statements():
    report = apply_citations(draft(), [source(1), source(2)])
    assert [t.text for t in report.key_trends] == ["Supported"]
    assert report.key_trends[0].source_ids == [1, 2]
    assert [c.name for c in report.competitors] == ["Lime"]
    assert report.whitespace_opportunities == []
    assert report.executive_summary_source_ids == [1]
    assert [s.id for s in report.sources] == [1, 2]


class FakeSearch:
    name = "fake"

    def __init__(self, results_by_query=None, fail=False):
        self.results_by_query = results_by_query or {}
        self.fail = fail
        self.queries = []

    async def search(self, query, max_results):
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("down")
        return self.results_by_query.get(query, [])


def result(url, content=LONG_TEXT):
    return SearchResult(url=url, title=url, snippet="", content=content)


async def test_discover_sources_interleaves_and_dedupes(monkeypatch):
    fake = FakeSearch({
        "scooters": [result("https://a.example/"), result("https://b.example")],
        "scooters market size and growth": [result("https://a.example"), result("https://c.example")],
    })
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)
    urls = [r.url for r in await discover_sources("scooters")]
    assert urls == ["https://a.example/", "https://b.example", "https://c.example"]
    assert len(fake.queries) == 4


@pytest.fixture
def pipeline(monkeypatch):
    """Stubs storage, retrieval and the LLM so the pipeline runs without external services."""
    stored, captured = [], {}

    async def fake_store(chunks, url, title=""):
        stored.append(url)

    async def fake_retrieve(query, top_k=5, urls=None):
        captured["urls"] = urls
        return [{"text": "Lime leads.", "metadata": {"url": u}} for u in (urls or ["https://old.example"])]

    async def fake_generate(query, chunks, source_ids):
        captured["source_ids"] = source_ids
        return draft(competitors=[competitor("Lime", [1])])

    async def fake_scrape(url):
        return LONG_TEXT

    monkeypatch.setattr(research, "store_documents", fake_store)
    monkeypatch.setattr(research, "retrieve_context", fake_retrieve)
    monkeypatch.setattr(research, "generate_research_report", fake_generate)
    monkeypatch.setattr(research, "scrape_core_content", fake_scrape)
    monkeypatch.setattr(research, "chunk_text", lambda text: [text])
    return stored, captured


async def test_run_research_cites_web_sources(monkeypatch, pipeline):
    stored, captured = pipeline
    fake = FakeSearch({"scooters": [result("https://a.example"), result("https://b.example", content=None)]})
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)
    events = []

    async def progress(stage, message):
        events.append(stage)

    report = await run_research("scooters", progress)
    assert stored == ["https://a.example", "https://b.example"]
    assert captured["urls"] == ["https://a.example", "https://b.example"]
    assert captured["source_ids"] == {"https://a.example": 1, "https://b.example": 2}
    assert [s.url for s in report.sources] == ["https://a.example", "https://b.example"]
    assert events[0] == "searching" and events[-1] == "writing"


async def test_run_research_needs_enough_sources(monkeypatch, pipeline):
    fake = FakeSearch({"scooters": [result("https://a.example"), result("https://thin.example", content="tiny")]})
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)

    async def thin_scrape(url):
        return "tiny"

    monkeypatch.setattr(research, "scrape_core_content", thin_scrape)
    with pytest.raises(InsufficientEvidence, match="Only 1 usable sources"):
        await run_research("scooters")


async def test_run_research_without_search_uses_stored_pages(monkeypatch, pipeline):
    monkeypatch.setattr(research, "get_search_provider", lambda: None)
    report = await run_research("scooters")
    assert [s.url for s in report.sources] == ["https://old.example"]
