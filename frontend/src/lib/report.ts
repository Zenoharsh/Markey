import type { MarketResearchReport } from '../types';

const LIST_FIELDS = [
  'key_figures', 'key_trends', 'growth_drivers', 'challenges', 'customer_segments', 'competitors',
  'competitive_forces', 'whitespace_opportunities', 'recommendations', 'data_gaps', 'sources',
] as const;

// Reports saved before a section existed simply lack it; show those sections as empty
export const normalizeReport = (raw: MarketResearchReport): MarketResearchReport => {
  const report = { ...raw } as MarketResearchReport;
  for (const field of LIST_FIELDS) {
    if (!Array.isArray(report[field])) (report as unknown as Record<string, unknown>)[field] = [];
  }
  report.competitors = report.competitors.map(c => ({
    ...c,
    pricing_model: c.pricing_model && c.pricing_model !== 'Unknown' ? c.pricing_model : null,
    target_audience: c.target_audience && c.target_audience !== 'Unknown' ? c.target_audience : null,
    scale: c.scale ?? null,
    market_share_percent: c.market_share_percent ?? null,
  }));
  // Briefs written before figures carried a segment: keep only clear whole-market figures as headline candidates
  report.key_figures = report.key_figures.map(f =>
    f.segment !== undefined
      ? f
      : {
          ...f,
          segment:
            f.kind === 'market_size' || f.kind === 'forecast' || (f.kind === 'growth_rate' && /market/i.test(f.label))
              ? null
              : f.label,
        },
  );
  report.removed_statements ??= 0;
  report.removed_figures ??= 0;
  return report;
};

export const formatFigure = (value: number, unit: string) => {
  const number = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return unit.trim() === '%' ? { value: `${number}%`, unit: '' } : { value: number, unit };
};
