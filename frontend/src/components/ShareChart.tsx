import React, { useState } from 'react';
import type { CompetitorData } from '../types';

const niceMax = (value: number) => Math.min(100, Math.max(10, Math.ceil(value / 10) * 10));

// Horizontal bars of each competitor's stated market share, largest first. One series, so one hue and
// no legend; the competitor table repeats every value.
export const ShareChart: React.FC<{ competitors: CompetitorData[] }> = ({ competitors }) => {
  const [active, setActive] = useState<string | null>(null);
  const rows = competitors
    .filter((c): c is CompetitorData & { market_share_percent: number } => c.market_share_percent !== null)
    .sort((a, b) => b.market_share_percent - a.market_share_percent);
  const max = niceMax(rows[0]?.market_share_percent ?? 0);
  const ticks = [0, 1, 2, 3, 4, 5].map(i => Math.round((max / 5) * i));

  return (
    <div className="chart" role="list" aria-label="Market share by competitor, in percent">
      {rows.map(c => {
        const pct = Math.min(c.market_share_percent / max, 1) * 100;
        return (
          <div
            key={c.name}
            className="chart-row"
            role="listitem"
            tabIndex={0}
            aria-label={`${c.name}: ${c.market_share_percent}% market share`}
            onPointerEnter={() => setActive(c.name)}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive(c.name)}
            onBlur={() => setActive(null)}
          >
            <span className="chart-name" title={c.name}>{c.name}</span>
            <div className="chart-track">
              <div className="chart-plot">
                <div className="chart-bar" style={{ width: `${pct}%` }} />
                <span className="chart-value" style={{ left: `${pct}%` }}>{c.market_share_percent}%</span>
                {active === c.name && (
                  <div className="tooltip" role="tooltip" style={{ left: `${Math.min(Math.max(pct, 20), 80)}%` }}>
                    <strong>{c.market_share_percent}%</strong>
                    {c.name}
                    {c.scale && <div style={{ marginTop: 4 }}>{c.scale}</div>}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
      <div className="chart-axis" aria-hidden="true">
        <span />
        <div className="chart-ticks">
          {ticks.map(t => <span key={t}>{t}%</span>)}
        </div>
      </div>
    </div>
  );
};
