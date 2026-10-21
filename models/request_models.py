from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

# What models write when they mean "no value"; stored as a real null so the UI never shows the word
_EMPTY = {"", "null", "none", "n/a", "na", "unknown", "not stated", "not available", "-"}


def _none_if_empty(value):
    if isinstance(value, str) and value.strip().lower() in _EMPTY:
        return None
    return value

class ScrapeRequest(BaseModel):
    url: HttpUrl
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://example.com"
                }
            ]
        }
    }

class ResearchQuery(BaseModel):
    query: str = Field(min_length=2, max_length=300)


class CitedText(BaseModel):
    text: str
    source_ids: list[int] = Field(description="IDs of the sources that support this statement")


class KeyFigure(BaseModel):
    """A number stated in the sources, such as a market size or growth rate."""
    label: str = Field(description="What the number measures, e.g. 'Global market size' or 'Forecast CAGR 2024-2030'")
    value: float = Field(description="The number exactly as written in the source, without unit words")
    unit: str = Field(description="e.g. 'USD billion', '%', 'million users'")
    year: int | None = Field(description="Year the figure refers to, if stated")
    kind: Literal["market_size", "forecast", "growth_rate", "market_share", "other"]
    segment: str | None = Field(
        description="The segment, region, product or company this figure is about; null when it is for the whole market"
    )
    related_market: str | None = Field(
        default=None,
        description="Name of the related or broader market this figure measures, when it is not the market asked about; "
        "null when it measures the asked market",
    )
    source_ids: list[int]

    _empty_to_none = field_validator("segment", "related_market", mode="before")(_none_if_empty)


class CompetitorData(BaseModel):
    name: str
    core_value_proposition: str = Field(description="What they offer and why customers choose them")
    pricing_model: str | None = Field(description="Pricing as stated in the sources, or null")
    target_audience: str | None
    scale: str | None = Field(description="Size indicators stated in the sources: revenue, funding, users, locations")
    market_share_percent: float | None = Field(description="Market share in percent, only if stated in the sources")
    source_ids: list[int] = Field(description="IDs of the sources this competitor's details come from")

    _empty_to_none = field_validator("pricing_model", "target_audience", "scale", mode="before")(_none_if_empty)

    @field_validator("core_value_proposition", mode="before")
    @classmethod
    def _blank_offering(cls, value):
        return _none_if_empty(value) or ""


class ForceAssessment(BaseModel):
    """One of Porter's five forces."""
    force: Literal[
        "Competitive rivalry", "Threat of new entrants", "Buyer power", "Supplier power", "Threat of substitutes"
    ]
    intensity: Literal["low", "medium", "high"]
    rationale: str
    source_ids: list[int]


class ReportDraft(BaseModel):
    """What the LLM writes. Every statement carries the IDs of the sources it came from."""
    industry_name: str
    executive_summary: str
    executive_summary_source_ids: list[int]
    key_figures: list[KeyFigure]
    key_trends: list[CitedText]
    growth_drivers: list[CitedText]
    challenges: list[CitedText] = Field(description="Restraints, risks and barriers")
    customer_segments: list[CitedText] = Field(description="Who buys, and what each segment needs")
    competitors: list[CompetitorData]
    competitive_forces: list[ForceAssessment]
    whitespace_opportunities: list[CitedText]
    recommendations: list[CitedText] = Field(description="Strategic moves for a company entering or competing in this market")
    data_gaps: list[str] = Field(description="Important questions the sources did not answer")


# What each research agent writes. Every agent sees the same numbered sources, so ids mean the same everywhere.

FOLLOW_UP = "Up to 3 web searches that would find what this section still lacks, e.g. the name of a market report; empty when nothing important is missing"


class MarketScope(BaseModel):
    """The scoping agent's definition of the market and the searches each research agent should run."""
    market_name: str = Field(description="The market the query is about, in a few words")
    definition: str = Field(description="One or two sentences on what the market includes and excludes")
    geography: str = Field(description="Where the research should focus, e.g. 'Global' or 'India'")
    adjacent_markets: list[str] = Field(description="Related or broader markets that may be sized when this one isn't")
    sizing_queries: list[str] = Field(description="3 web searches for market size, forecasts and growth rates")
    competition_queries: list[str] = Field(description="3 web searches for the leading companies, their offers, pricing and shares")
    demand_queries: list[str] = Field(description="3 web searches for customer segments, buying needs and demand drivers")
    trends_queries: list[str] = Field(description="3 web searches for trends, technology shifts, regulation and risks")


class SizingSection(BaseModel):
    key_figures: list[KeyFigure]
    data_gaps: list[str]
    follow_up_queries: list[str] = Field(description=FOLLOW_UP)


class CompetitionSection(BaseModel):
    competitors: list[CompetitorData]
    competitive_forces: list[ForceAssessment]
    data_gaps: list[str]
    follow_up_queries: list[str] = Field(description=FOLLOW_UP)


class DemandSection(BaseModel):
    customer_segments: list[CitedText] = Field(description="Who buys, and what each segment needs")
    growth_drivers: list[CitedText]
    data_gaps: list[str]
    follow_up_queries: list[str] = Field(description=FOLLOW_UP)


class TrendsSection(BaseModel):
    key_trends: list[CitedText]
    challenges: list[CitedText] = Field(description="Restraints, risks and barriers")
    data_gaps: list[str]
    follow_up_queries: list[str] = Field(description=FOLLOW_UP)


class StrategySection(BaseModel):
    executive_summary: str
    executive_summary_source_ids: list[int]
    whitespace_opportunities: list[CitedText]
    recommendations: list[CitedText]


class Source(BaseModel):
    id: int
    url: str
    title: str
    retrieved_at: str

class MarketResearchReport(ReportDraft):
    """The report returned to clients: the draft with unsupported claims removed, plus its sources."""
    sources: list[Source] = []
    # What the scoping agent took the market to be
    market_definition: str = ""
    # Counts from the verification step, shown in the report's methodology note
    removed_statements: int = 0
    removed_figures: int = 0
