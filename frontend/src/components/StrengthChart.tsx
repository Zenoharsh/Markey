import React, { useState } from 'react';
import type { CompetitorData } from '../types';

const TICKS = [0, 2, 4, 6, 8, 10];

// Horizontal bars of each competitor's 0-10 strength score, strongest first. The competitor table
// below repeats every value, so the tooltip only adds detail.
export const StrengthChart: React.FC<{ competitors: CompetitorData[] }> = ({ competitors }) => {
  const [active, setActive] = useState<string | null>(null);
  const rows = [...competitors].sort((a, b) => b.market_strength_score - a.market_strength_score);

  return (
    <div className="chart" role="list" aria-label="Market strength score by competitor, out of 10">
      {rows.map(c => {
        const pct = Math.min(Math.max(c.market_strength_score, 0), 10) * 10;
        return (
          <div
            key={c.name}
            className="chart-row"
            role="listitem"
            tabIndex={0}
            aria-label={`${c.name}: ${c.market_strength_score} out of 10`}
            onPointerEnter={() => setActive(c.name)}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive(c.name)}
            onBlur={() => setActive(null)}
          >
            <span className="chart-name" title={c.name}>{c.name}</span>
            <div className="chart-track">
              <div className="chart-plot">
                <div className="chart-bar" style={{ width: `${pct}%` }} />
                <span className="chart-value" style={{ left: `${pct}%` }}>{c.market_strength_score}</span>
                {active === c.name && (
                  <div className="tooltip" role="tooltip" style={{ left: `${Math.min(Math.max(pct, 20), 80)}%` }}>
                    <strong>{c.market_strength_score} / 10</strong>
                    {c.name}
                    <div style={{ marginTop: 4 }}>{c.pricing_model}</div>
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
          {TICKS.map(t => <span key={t}>{t}</span>)}
        </div>
      </div>
    </div>
  );
};
