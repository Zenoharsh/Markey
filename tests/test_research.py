import pytest

from models.request_models import (
    CitedText,
    CompetitionSection,
    CompetitorData,
    DemandSection,
    ForceAssessment,
    KeyFigure,
    MarketScope,
    ReportDraft,
    SizingSection,
    Source,
    StrategySection,
    TrendsSection,
)
from services import research
from services.research import (
    InsufficientEvidence,
    apply_citations,
    gather_evidence,
    number_stated,
    run_research,
    search_all,
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
    return KeyFigure(label=label, value=value, unit="USD billion", year=2025, kind="market_size", segment=None, source_ids=ids)


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


async def test_gather_evidence_covers_every_query_within_budget(monkeypatch):
    queries = []

    async def fake_retrieve(query, top_k=5, urls=None):
        queries.append(query)
        return [{"text": f"{query} #{i}", "metadata": {"url": "https://a.example"}} for i in range(top_k)]

    monkeypatch.setattr(research, "retrieve_context", fake_retrieve)
    chunks = await gather_evidence(["a", "b", "c", "d", "e"], ["https://a.example"], budget=6)
    assert len(chunks) == 6
    # The first passage of every query is kept before second-best ones
    assert {c["text"] for c in chunks[:5]} == {f"{q} #0" for q in queries}


class FakeSearch:
    name = "fake"

    def __init__(self, results_by_query=None, default=None, fail=False):
        self.results_by_query = results_by_query or {}
        self.default = default or []
        self.fail = fail
        self.queries = []

    async def search(self, query, max_results):
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("down")
        return self.results_by_query.get(query, self.default)


def result(url, content=LONG_TEXT):
    return SearchResult(url=url, title=url, snippet="", content=content)


async def test_search_all_interleaves_and_dedupes():
    fake = FakeSearch({
        "scooters": [result("https://a.example/"), result("https://b.example")],
        "scooter market size": [result("https://a.example"), result("https://c.example")],
    })
    urls = [r.url for r in await search_all(fake, ["scooters", "scooter market size"])]
    assert urls == ["https://a.example/", "https://b.example", "https://c.example"]


def scope(**overrides):
    values = dict(
        market_name="Scooter sharing", definition="Shared electric scooters rented by the minute.", geography="Global",
        adjacent_markets=["Bike sharing"], sizing_queries=["scooter sharing market size"], competition_queries=[],
        demand_queries=[], trends_queries=[],
    )
    return MarketScope(**(values | overrides))


class FakeLLM:
    """Answers each agent by the schema it asks for; a list of answers is used in turn."""

    def __init__(self, **answers):
        self.answers = {
            "MarketScope": scope(),
            "SizingSection": SizingSection(key_figures=[figure(12.5, [1])], data_gaps=["No regional split"], follow_up_queries=[]),
            "CompetitionSection": CompetitionSection(
                competitors=[competitor("Lime", [1])], competitive_forces=[], data_gaps=[], follow_up_queries=[]
            ),
            "DemandSection": DemandSection(customer_segments=[], growth_drivers=[], data_gaps=[], follow_up_queries=[]),
            "TrendsSection": TrendsSection(
                key_trends=[CitedText(text="Cities cap fleets", source_ids=[2])], challenges=[], data_gaps=[], follow_up_queries=[]
            ),
            "StrategySection": StrategySection(
                executive_summary="Growing.", executive_summary_source_ids=[1],
                whitespace_opportunities=[],
                recommendations=[CitedText(text="Partner with cities", source_ids=[1]), CitedText(text="Made up", source_ids=[99])],
            ),
        } | answers
        self.calls = []

    async def generate_structured(self, prompt, schema):
        self.calls.append(schema.__name__)
        answer = self.answers[schema.__name__]
        if isinstance(answer, list):
            answer = answer.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def pipeline(monkeypatch):
    """Stubs storage, retrieval and the LLM so the pipeline runs without external services."""
    stored, captured = [], {"urls": []}
    llm = FakeLLM()

    async def fake_store(chunks, url, title=""):
        stored.append(url)

    async def fake_retrieve(query, top_k=5, urls=None):
        captured["urls"].append(urls)
        text = "The market reached USD 12.5 billion. Lime leads."
        return [{"text": text, "metadata": {"url": u}} for u in (urls or ["https://old.example"])]

    async def fake_scrape(url):
        return LONG_TEXT

    monkeypatch.setattr(research, "store_documents", fake_store)
    monkeypatch.setattr(research, "retrieve_context", fake_retrieve)
    monkeypatch.setattr(research, "get_llm_provider", lambda: llm)
    monkeypatch.setattr(research, "scrape_core_content", fake_scrape)
    monkeypatch.setattr(research, "chunk_text", lambda text: [text])
    return stored, captured, llm


async def test_agents_research_in_parallel_and_share_numbered_sources(monkeypatch, pipeline):
    stored, captured, llm = pipeline
    fake = FakeSearch(
        {"scooters": [result("https://a.example"), result("https://b.example", content=None)]},
        default=[result("https://a.example"), result("https://c.example")],
    )
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)
    events = []

    async def progress(stage, message, agent=None, done=False):
        events.append((stage, agent, done))

    report = await run_research("scooters", progress)
    # Each page is read once, however many agents found it
    assert stored == ["https://a.example", "https://b.example", "https://c.example"]
    assert [s.id for s in report.sources] == [1, 2, 3]
    assert llm.calls[0] == "MarketScope" and llm.calls[-1] == "StrategySection"
    assert sorted(llm.calls[1:-1]) == ["CompetitionSection", "DemandSection", "SizingSection", "TrendsSection"]
    assert "scooter sharing market size" in fake.queries
    assert report.industry_name == "Scooter sharing"
    assert report.market_definition.startswith("Shared electric scooters")
    assert [f.value for f in report.key_figures] == [12.5]
    assert [c.name for c in report.competitors] == ["Lime"]
    assert [r.text for r in report.recommendations] == ["Partner with cities"]
    assert report.removed_statements == 1
    assert report.data_gaps == ["No regional split"]
    assert events[0][0] == "scoping" and events[-1][0] == "writing"
    assert {agent for stage, agent, done in events if done} == {"sizing", "competition", "demand", "trends"}


async def test_an_analyst_searches_again_when_its_section_is_missing_essentials(monkeypatch, pipeline):
    _, _, llm = pipeline
    llm.answers["SizingSection"] = [
        SizingSection(key_figures=[], data_gaps=[], follow_up_queries=["scooter sharing market report"]),
        SizingSection(key_figures=[figure(12.5, [1])], data_gaps=[], follow_up_queries=[]),
    ]
    fake = FakeSearch(default=[result("https://a.example"), result("https://b.example")])
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)
    report = await run_research("scooters")
    assert "scooter sharing market report" in fake.queries
    assert llm.calls.count("SizingSection") == 2
    assert [f.value for f in report.key_figures] == [12.5]


async def test_a_failed_analyst_leaves_a_gap_instead_of_failing_the_report(monkeypatch, pipeline):
    _, _, llm = pipeline
    llm.answers["DemandSection"] = RuntimeError("model overloaded")
    fake = FakeSearch(default=[result("https://a.example"), result("https://b.example")])
    monkeypatch.setattr(research, "get_search_provider", lambda: fake)
    report = await run_research("scooters")
    assert "The customers and demand research could not be completed this time." in report.data_gaps
    assert [c.name for c in report.competitors] == ["Lime"]


async def test_findings_survive_a_failed_strategist(monkeypatch, pipeline):
    _, _, llm = pipeline
    llm.answers["StrategySection"] = RuntimeError("model overloaded")
    monkeypatch.setattr(research, "get_search_provider", lambda: FakeSearch(default=[result("https://a.example"), result("https://b.example")]))
    report = await run_research("scooters")
    assert report.executive_summary.startswith("The summary could not be written")
    assert [f.value for f in report.key_figures] == [12.5]


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
    monkeypatch.setenv("RESEARCH_MIN_SOURCES", "1")
    report = await run_research("scooters")
    assert [s.url for s in report.sources] == ["https://old.example"]


def test_null_words_become_real_nulls():
    c = CompetitorData(
        name="Zappi", core_value_proposition="null", pricing_model="null", target_audience="Unknown",
        scale="N/A", market_share_percent=None, source_ids=[1],
    )
    assert (c.core_value_proposition, c.pricing_model, c.target_audience, c.scale) == ("", None, None, None)
    f = KeyFigure(
        label="Size", value=5, unit="USD billion", year=2024, kind="market_size", segment="null",
        related_market="none", source_ids=[1],
    )
    assert f.segment is None and f.related_market is None


def test_related_market_figures_are_kept():
    sources = [Source(id=1, url="https://a.example", title="A", retrieved_at="")]
    figure = KeyFigure(
        label="Marketing automation software market", value=6.65, unit="USD billion", year=2024,
        kind="market_size", segment=None, related_market="Marketing automation software", source_ids=[1],
    )
    report = apply_citations(draft(key_figures=[figure]), sources, {1: "valued at USD 6.65 billion in 2024"})
    assert report.key_figures[0].related_market == "Marketing automation software"
