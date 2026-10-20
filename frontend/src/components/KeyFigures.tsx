import React, { useState } from 'react';
import type { KeyFigure, Source } from '../types';
import { Citations } from './Citations';
import { formatFigure } from '../lib/report';
import { headlines, range, sizeSeries, type Headline } from '../lib/figures';

const fmt = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 2 });

const shown = (f: KeyFigure) => {
  const parts = formatFigure(f.value, f.unit);
  return parts.unit ? `${parts.value} ${parts.unit}` : parts.value;
};

const uniqueIds = (figures: KeyFigure[]) => [...new Set(figures.flatMap(f => f.source_ids))].sort((a, b) => a - b);

// One big number per question; a range when sources disagree, with how many estimates it spans
const HeadlineTile: React.FC<{ headline: Headline; sources: Source[] }> = ({ headline, sources }) => {
  const { min, max } = range(headline.figures);
  const unit = headline.figures[0].unit;
  const percent = unit.trim() === '%';
  const value = min === max ? fmt(min) : `${fmt(min)}–${fmt(max)}`;
  const ids = uniqueIds(headline.figures);
  const estimates = headline.figures.length;

  return (
    <div className="headline">
      <div className="figure-kind">{headline.title}</div>
      <div className="headline-value">
        {value}
        {percent ? '%' : <span className="figure-unit"> {unit}</span>}
      </div>
      <div className="figure-label">
        {estimates > 1
          ? `${estimates} estimates from ${ids.length} source${ids.length === 1 ? '' : 's'}`
          : headline.figures[0].label}
        <Citations ids={ids} sources={sources} />
      </div>
      {headline.others > 0 && (
        <div className="headline-note">
          {headline.others} more forecast{headline.others === 1 ? '' : 's'} for other years in the table below
        </div>
      )}
    </div>
  );
};

const SizeChart: React.FC<{ series: KeyFigure[]; source?: Source }> = ({ series, source }) => {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(...series.map(f => f.value));
  const hasForecast = series.some(f => f.kind === 'forecast');
  const hasReported = series.some(f => f.kind !== 'forecast');

  return (
    <figure className="size-chart">
      <figcaption>
        <span>
          <span className="size-title">Market size, {series[0].unit}</span>
          {source && <span className="size-source">From source {source.id}, {source.title}</span>}
        </span>
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
            aria-label={`${f.year}: ${shown(f)}${f.kind === 'forecast' ? ', forecast' : ''}`}
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
                  <strong>{shown(f)}</strong>
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

const FigureTable: React.FC<{ figures: KeyFigure[]; sources: Source[]; segmentColumn?: boolean }> = ({
  figures, sources, segmentColumn,
}) => (
  <div className="table-wrap">
    <table className="figure-table">
      <thead>
        <tr>
          {segmentColumn && <th scope="col">Segment</th>}
          <th scope="col">Measure</th>
          <th scope="col">Value</th>
          <th scope="col">Year</th>
          <th scope="col">Source</th>
        </tr>
      </thead>
      <tbody>
        {figures.map((f, i) => (
          <tr key={i}>
            {segmentColumn && <td className="name">{f.segment ?? 'Whole market'}</td>}
            <td>{segmentColumn && f.label === f.segment ? '' : f.label}</td>
            <td className="num">{shown(f)}</td>
            <td className="num-plain">{f.year ?? ''}</td>
            <td><Citations ids={f.source_ids} sources={sources} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export const KeyFigures: React.FC<{ figures: KeyFigure[]; sources: Source[] }> = ({ figures, sources }) => {
  const tops = headlines(figures);
  const chart = sizeSeries(figures);
  const segments = figures.filter(f => f.segment);
  const rest = figures.filter(f => !f.segment);

  return (
    <>
      {tops.length > 0 && (
        <div className="headlines">
          {tops.map(h => <HeadlineTile key={h.title} headline={h} sources={sources} />)}
        </div>
      )}
      {chart && <SizeChart series={chart.series} source={sources.find(s => s.id === chart.sourceId)} />}
      {segments.length > 0 && (
        <div className="figure-block">
          <h3 className="sub-heading">By segment</h3>
          <FigureTable figures={segments} sources={sources} segmentColumn />
        </div>
      )}
      {rest.length > 0 && (
        <details className="figure-block">
          <summary>Every whole-market figure ({rest.length})</summary>
          <FigureTable figures={rest} sources={sources} />
        </details>
      )}
    </>
  );
};
