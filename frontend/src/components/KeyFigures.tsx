import React, { useState } from 'react';
import type { KeyFigure, Source } from '../types';
import { Citations } from './Citations';
import { formatFigure } from '../lib/report';

const KIND_LABEL: Record<KeyFigure['kind'], string> = {
  market_size: 'Market size',
  forecast: 'Forecast',
  growth_rate: 'Growth',
  market_share: 'Market share',
  other: 'Figure',
};

// Market size by year when the sources give at least two years in the same unit
const sizeSeries = (figures: KeyFigure[]) => {
  const byUnit = new Map<string, KeyFigure[]>();
  for (const f of figures) {
    if ((f.kind === 'market_size' || f.kind === 'forecast') && f.year !== null) {
      const key = f.unit.trim().toLowerCase();
      byUnit.set(key, [...(byUnit.get(key) ?? []), f]);
    }
  }
  const best = [...byUnit.values()].sort((a, b) => b.length - a.length)[0] ?? [];
  const byYear = new Map<number, KeyFigure>();
  for (const f of best) if (!byYear.has(f.year!)) byYear.set(f.year!, f);
  return [...byYear.values()].sort((a, b) => a.year! - b.year!);
};

const SizeChart: React.FC<{ series: KeyFigure[] }> = ({ series }) => {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(...series.map(f => f.value));
  const hasForecast = series.some(f => f.kind === 'forecast');
  const hasReported = series.some(f => f.kind !== 'forecast');

  return (
    <figure className="size-chart">
      <figcaption>
        <span className="size-title">Market size, {series[0].unit}</span>
        {hasForecast && hasReported && (
          <span className="legend">
            <span><i className="swatch" /> Reported</span>
            <span><i className="swatch swatch-forecast" /> Forecast</span>
          </span>
        )}
      </figcaption>
      <div className="columns" role="list" aria-label={`Market size by year, ${series[0].unit}`}>
        {series.map(f => (
          <div
            key={f.year}
            className="column"
            role="listitem"
            tabIndex={0}
            aria-label={`${f.year}: ${formatFigure(f.value, f.unit).value} ${f.unit}${f.kind === 'forecast' ? ', forecast' : ''}`}
            onPointerEnter={() => setActive(f.year)}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive(f.year)}
            onBlur={() => setActive(null)}
          >
            <div className="column-plot">
              <span className="column-value">{formatFigure(f.value, f.unit).value}</span>
              <div
                className={`column-bar${f.kind === 'forecast' ? ' column-forecast' : ''}`}
                style={{ height: `${(f.value / max) * 100}%` }}
              />
              {active === f.year && (
                <div className="tooltip column-tooltip" role="tooltip">
                  <strong>{formatFigure(f.value, f.unit).value} {formatFigure(f.value, f.unit).unit}</strong>
                  {f.year}{f.kind === 'forecast' ? ' forecast' : ''}
                  <div style={{ marginTop: 4 }}>{f.label}</div>
                </div>
              )}
            </div>
            <span className="column-label">{f.year}</span>
          </div>
        ))}
      </div>
    </figure>
  );
};

export const KeyFigures: React.FC<{ figures: KeyFigure[]; sources: Source[] }> = ({ figures, sources }) => {
  const series = sizeSeries(figures);
  return (
    <>
      <div className="figures">
        {figures.map((f, i) => {
          const shown = formatFigure(f.value, f.unit);
          return (
            <div key={i} className="figure">
              <div className="figure-kind">{KIND_LABEL[f.kind]}{f.year ? ` · ${f.year}` : ''}</div>
              <div className="figure-value">
                {shown.value}
                {shown.unit && <span className="figure-unit"> {shown.unit}</span>}
              </div>
              <div className="figure-label">
                {f.label}
                <Citations ids={f.source_ids} sources={sources} />
              </div>
            </div>
          );
        })}
      </div>
      {series.length >= 2 && <SizeChart series={series} />}
    </>
  );
};
