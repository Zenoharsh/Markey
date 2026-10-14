from pydantic import BaseModel, Field, HttpUrl

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

class CompetitorData(BaseModel):
    name: str
    pricing_model: str
    core_value_proposition: str
    target_audience: str
    market_strength_score: int
    source_ids: list[int] = Field(description="IDs of the sources this competitor's details come from")

class ReportDraft(BaseModel):
    """What the LLM writes. Every statement carries the IDs of the sources it came from."""
    industry_name: str
    executive_summary: str
    executive_summary_source_ids: list[int]
    key_trends: list[CitedText]
    competitors: list[CompetitorData]
    whitespace_opportunities: list[CitedText]

class Source(BaseModel):
    id: int
    url: str
    title: str
    retrieved_at: str

class MarketResearchReport(ReportDraft):
    """The report returned to clients: the draft with unsupported claims removed, plus its sources."""
    sources: list[Source] = []
