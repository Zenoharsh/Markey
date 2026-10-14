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
  | { type: 'job'; id: string }
  | { type: 'progress'; stage: string; message: string }
  | { type: 'report'; id: string; report: MarketResearchReport }
  | { type: 'error'; status: number; detail: string };

export type RunStatus = 'running' | 'done' | 'failed';

// One saved research run, as listed in history
export interface RunSummary {
  id: string;
  topic: string;
  status: RunStatus;
  created_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  industry_name: string | null;
  source_count: number;
  error: string | null;
}

export interface RunDetail extends RunSummary {
  error_status: number | null;
  report: MarketResearchReport | null;
}
