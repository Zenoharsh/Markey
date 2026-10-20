import React from 'react';
import type { CompetitorData, Source } from '../types';
import { Citations } from './Citations';

const NotStated = () => <span className="not-stated">Not stated</span>;

// Largest stated share first, then the rest in the order the sources gave them
export const CompetitorTable: React.FC<{ competitors: CompetitorData[]; sources: Source[] }> = ({ competitors, sources }) => {
  const rows = [...competitors].sort((a, b) => (b.market_share_percent ?? -1) - (a.market_share_percent ?? -1));
  // Columns the sources said nothing about for any company are left out rather than filled with "Not stated"
  const showShare = rows.some(c => c.market_share_percent !== null);
  const showPricing = rows.some(c => c.pricing_model);
  const showAudience = rows.some(c => c.target_audience);
  const showScale = rows.some(c => c.scale);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Company</th>
            <th scope="col">Offering</th>
            {showPricing && <th scope="col">Pricing</th>}
            {showAudience && <th scope="col">Target customers</th>}
            {showScale && <th scope="col">Scale</th>}
            {showShare && <th scope="col">Share</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map(c => (
            <tr key={c.name}>
              <td className="name">
                {c.name}
                <Citations ids={c.source_ids} sources={sources} />
              </td>
              <td>{c.core_value_proposition}</td>
              {showPricing && <td>{c.pricing_model ?? <NotStated />}</td>}
              {showAudience && <td>{c.target_audience ?? <NotStated />}</td>}
              {showScale && <td>{c.scale ?? <NotStated />}</td>}
              {showShare && (
                <td className="num">{c.market_share_percent !== null ? `${c.market_share_percent}%` : <NotStated />}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
