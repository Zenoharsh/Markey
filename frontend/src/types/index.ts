export interface CitedText {
  text: string;
  source_ids: number[];
}

export interface CompetitorData {
  name: string;
  pricing_model: string;
  core_value_proposition: string;
  target_audience: string;
  market_strength_score: number;
  source_ids: number[];
}

export interface Source {
  id: number;
  url: string;
  title: string;
  retrieved_at: string;
}

export interface MarketResearchReport {
  industry_name: string;
  executive_summary: string;
  executive_summary_source_ids: number[];
  key_trends: CitedText[];
  competitors: CompetitorData[];
  whitespace_opportunities: CitedText[];
  sources: Source[];
}

export type ResearchEvent =
  | { type: 'progress'; stage: string; message: string }
  | { type: 'report'; report: MarketResearchReport }
  | { type: 'error'; status: number; detail: string };
