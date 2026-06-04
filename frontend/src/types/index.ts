export interface CompetitorData {
  name: string;
  pricing_model: string;
  core_value_proposition: string;
  target_audience: string;
  market_strength_score: number;
}

export interface MarketResearchReport {
  industry_name: string;
  executive_summary: string;
  key_trends: string[];
  competitors: CompetitorData[];
  whitespace_opportunities: string[];
}
