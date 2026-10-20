import type { KeyFigure } from '../types';

export const unitKey = (unit: string) => unit.trim().toLowerCase();

const mostCommonUnit = (figures: KeyFigure[]) => {
  const counts = new Map<string, number>();
  for (const f of figures) counts.set(unitKey(f.unit), (counts.get(unitKey(f.unit)) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
};

export interface Headline {
  title: string;
  figures: KeyFigure[];
  // How many other figures of this kind exist but aren't in the headline (e.g. forecasts for other years)
  others: number;
}

// Up to three numbers a reader can take in at a glance: latest market size, furthest forecast, growth rate.
// Where sources disagree, the headline keeps every estimate and the tile shows their range.
export const headlines = (figures: KeyFigure[]): Headline[] => {
  const market = figures.filter(f => !f.segment);
  const out: Headline[] = [];

  const sizes = market.filter(f => f.kind === 'market_size' && f.year !== null);
  const sizeUnit = mostCommonUnit(sizes);
  const sameUnitSizes = sizes.filter(f => unitKey(f.unit) === sizeUnit);
  if (sameUnitSizes.length) {
    const thisYear = new Date().getFullYear();
    const years = sameUnitSizes.map(f => f.year!);
    const past = years.filter(y => y <= thisYear);
    const year = past.length ? Math.max(...past) : Math.min(...years);
    const atYear = sameUnitSizes.filter(f => f.year === year);
    out.push({ title: `Market size, ${year}`, figures: atYear, others: 0 });
  }

  const forecasts = market.filter(f => f.kind === 'forecast' && f.year !== null);
  const forecastUnit = mostCommonUnit(forecasts);
  const sameUnitForecasts = forecasts.filter(f => unitKey(f.unit) === forecastUnit);
  if (sameUnitForecasts.length) {
    const year = Math.max(...sameUnitForecasts.map(f => f.year!));
    const atYear = sameUnitForecasts.filter(f => f.year === year);
    out.push({ title: `Forecast, ${year}`, figures: atYear, others: forecasts.length - atYear.length });
  }

  const growth = market.filter(f => f.kind === 'growth_rate');
  if (growth.length) out.push({ title: 'Growth rate (CAGR)', figures: growth, others: 0 });

  return out;
};

// One source's market size path over time, so the chart never mixes different firms' estimates
export const sizeSeries = (figures: KeyFigure[]) => {
  const points = figures.filter(
    f => !f.segment && (f.kind === 'market_size' || f.kind === 'forecast') && f.year !== null && f.source_ids.length,
  );
  const bySource = new Map<number, KeyFigure[]>();
  for (const f of points) {
    const id = f.source_ids[0];
    bySource.set(id, [...(bySource.get(id) ?? []), f]);
  }
  let best: { sourceId: number; series: KeyFigure[] } | null = null;
  for (const [sourceId, list] of bySource) {
    const unit = mostCommonUnit(list);
    const byYear = new Map<number, KeyFigure>();
    for (const f of list) if (unitKey(f.unit) === unit && !byYear.has(f.year!)) byYear.set(f.year!, f);
    const series = [...byYear.values()].sort((a, b) => a.year! - b.year!);
    if (!best || series.length > best.series.length) best = { sourceId, series };
  }
  return best && best.series.length >= 2 ? best : null;
};

export const range = (figures: KeyFigure[]) => {
  const values = figures.map(f => f.value);
  return { min: Math.min(...values), max: Math.max(...values) };
};
