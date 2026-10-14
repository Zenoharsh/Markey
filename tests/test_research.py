import pytest

from models.request_models import CitedText, CompetitorData, ForceAssessment, KeyFigure, ReportDraft, Source
from services import research
from services.research import (
    InsufficientEvidence,
    apply_citations,
    discover_sources,
    gather_evidence,
    number_stated,
    run_research,
)
from services.search import SearchResult

LONG_TEXT = "Scooter sharing keeps growing in cities. " * 30


def source(i):
    return Source(id=i, url=f"https://s{i}.example", title=f"S{i}", retrieved_at="2026-10-14T00:00:00+00:00")


def competitor(name, ids, share=None):
    return CompetitorData(
        name=name, pricing_model="Per minute", core_value_proposition="Fast", target_audience="Commuters",
        scale=None, market_share_percent=share, source_ids=ids,
    )


def figure(value, ids, label="Market size"):
    return KeyFigure(label=label, value=value, unit="USD billion", year=2025, kind="market_size", source_ids=ids)


def draft(**overrides):
    values = dict(
        industry_name="Micromobility",
        executive_summary="Growing.",
        executive_summary_source_ids=[1, 9],
        key_trends=[CitedText(text="Supported", source_ids=[2, 2, 1]), CitedText(text="Made up", source_ids=[])],
        key_figures=[],
        growth_drivers=[],
        challenges=[],
        customer_segments=[],
        competitors=[competitor("Lime", [1]), competitor("Ghost Co", [7])],
        competitive_forces=[
            ForceAssessment(force="Buyer power", intensity="high", rationale="Riders switch apps freely", source_ids=[2]),
            ForceAssessment(force="Supplier power", intensity="low", rationale="Unsupported", source_ids=[]),
        ],
        whitespace_opportunities=[CitedText(text="Bad citation", source_ids=[42])],
        recommendations=[CitedText(text="Partner with cities", source_ids=[1])],
        data_gaps=["No regional split", "  "],
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
    assert [f.force for f in report.competitive_forces] == ["Buyer power"]
    assert [r.text for r in report.recommendations] == ["Partner with cities"]
    assert report.data_gaps == ["No regional split"]
    assert [s.id for s in report.sources] == [1, 2]
    # Made up trend, Ghost Co, bad-citation opportunity and the uncited force
    assert report.removed_statements == 4


def test_figures_must_appear_in_the_cited_passages():
    evidence = {1: "The market reached USD 12.5 billion in 2025, and Lime holds 31% of rides.", 2: "Grew 8% a year."}
    report = apply_citations(
        draft(
            key_figures=[figure(12.5, [1]), figure(40, [1], "Invented"), figure(12.5, [2], "Wrong source")],
            competitors=[competitor("Lime", [1], share=31), competitor("Bird", [1], share=20)],
        ),
        [source(1), source(2)],
        evidence,
    )
    assert [f.label for f in report.key_figures] == ["Market size"]
    assert [c.market_share_percent for c in report.competitors] == [31, None]
    assert report.removed_figures == 3


@pytest.mark.parametrize(
    "value, text, expected",
    [
        (12.5, "worth $12.5 billion", True),
        (12.5, "worth $112.5 billion", False),
        (5, "about 5.2 million", False),
        (1200, "1,200 stations", True),
        (8.0, "grew 8% a year", True),
        (0.25, "a 0.25 point rise", True),
    ],
)
def test_number_stated(value, text, expected):
    assert number_stated(value, text) is expected


async def test_gather_evidence_covers_every_theme_within_budget(monkeypatch):
    monkeypatch.setenv("CONTEXT_CHUNKS", "6")
    queries = []

    async def fake_retrieve(query, top_k=5, urls=None):
        queries.append(query)
        return [{"text": f"{query} #{i}", "metadata": {"url": "https://a.example"}} for i in range(top_k)]

    monkeypatch.setattr(research, "retrieve_context", fake_retrieve)
    chunks = await gather_evidence("scooters", ["https://a.example"])
    assert len(chunks) == 6
    # The first passage of every theme is kept before second-best ones
    assert {c["text"] for c in chunks[:5]} == {f"{q} #0" for q in queries}


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
        "scooters market size and growth forecast CAGR": [result("https://a.example"), result("https://c.example")],
    })
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)
    urls = [r.url for r in await discover_sources("scooters")]
    assert urls == ["https://a.example/", "https://b.example", "https://c.example"]
    assert len(fake.queries) == 6


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
