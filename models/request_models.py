from pydantic import BaseModel, HttpUrl

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
    query: str

class CompetitorData(BaseModel):
    name: str
    pricing_model: str
    core_value_proposition: str
    target_audience: str
    market_strength_score: int

class MarketResearchReport(BaseModel):
    industry_name: str
    executive_summary: str
    key_trends: list[str]
    competitors: list[CompetitorData]
    whitespace_opportunities: list[str]
