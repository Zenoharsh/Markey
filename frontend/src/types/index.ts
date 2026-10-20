export interface CitedText {
  text: string;
  source_ids: number[];
}

export interface KeyFigure {
  label: string;
  value: number;
  unit: string;
  year: number | null;
  kind: 'market_size' | 'forecast' | 'growth_rate' | 'market_share' | 'other';
  // The segment, region or company the figure is about; null for the whole market
  segment: string | null;
  // Set when the figure measures a related or broader market, given as context when the asked market wasn't sized
  related_market?: string | null;
  source_ids: number[];
}

export interface CompetitorData {
  name: string;
  core_value_proposition: string;
  pricing_model: string | null;
  target_audience: string | null;
  scale: string | null;
  market_share_percent: number | null;
  source_ids: number[];
}

export type Intensity = 'low' | 'medium' | 'high';

export interface ForceAssessment {
  force: string;
  intensity: Intensity;
  rationale: string;
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
  key_figures: KeyFigure[];
  key_trends: CitedText[];
  growth_drivers: CitedText[];
  challenges: CitedText[];
  customer_segments: CitedText[];
  competitors: CompetitorData[];
  competitive_forces: ForceAssessment[];
  whitespace_opportunities: CitedText[];
  recommendations: CitedText[];
  data_gaps: string[];
  sources: Source[];
  removed_statements: number;
  removed_figures: number;
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
