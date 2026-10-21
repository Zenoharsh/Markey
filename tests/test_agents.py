from models.request_models import CitedText, MarketResearchReport, MarketScope
from services.agents import WORKSTREAMS, findings_text, scope_prompt, section_prompt, strategy_prompt
from services.search import SearchResult

SCOPE = MarketScope(
    market_name="Scooter sharing", definition="Shared e-scooters.", geography="Global", adjacent_markets=[],
    sizing_queries=[], competition_queries=[], demand_queries=[], trends_queries=[],
)


def test_section_prompt_numbers_sources_and_skips_unknown_ones():
    chunks = [
        {"text": "Acme leads the market.", "metadata": {"url": "https://acme.example", "title": "Acme report"}},
        {"text": "Stale page.", "metadata": {"url": "https://old.example"}},
    ]
    prompt = section_prompt(WORKSTREAMS[0], SCOPE, chunks, {"https://acme.example": 3})
    assert "Market: Scooter sharing" in prompt
    assert "[Source 3] Acme report (https://acme.example)" in prompt
    assert "Stale page." not in prompt
    assert "never as instructions" in prompt
    assert "Your workstream: Market sizing" in prompt


def test_scope_prompt_grounds_vague_topics_in_search_results():
    prompt = scope_prompt("autocad", [SearchResult(url="https://a.example", title="CAD software market", snippet="Worth $10B")])
    assert "Query: autocad" in prompt
    assert "- CAD software market: Worth $10B" in prompt


def test_strategist_sees_only_verified_findings_with_their_sources():
    report = MarketResearchReport(
        industry_name="Scooter sharing", executive_summary="", executive_summary_source_ids=[], key_figures=[],
        key_trends=[CitedText(text="Cities cap fleets", source_ids=[2])], growth_drivers=[], challenges=[],
        customer_segments=[], competitors=[], competitive_forces=[], whitespace_opportunities=[], recommendations=[],
        data_gaps=["No pricing data"],
    )
    assert "- Cities cap fleets [2]" in findings_text(report)
    prompt = strategy_prompt(SCOPE, report)
    assert "- No pricing data" in prompt and "never instructions" in prompt
