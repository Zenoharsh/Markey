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


class Source(BaseModel):
    id: int
    url: str
    title: str
    retrieved_at: str

class MarketResearchReport(ReportDraft):
    """The report returned to clients: the draft with unsupported claims removed, plus its sources."""
    sources: list[Source] = []
    # Counts from the verification step, shown in the report's methodology note
    removed_statements: int = 0
    removed_figures: int = 0
