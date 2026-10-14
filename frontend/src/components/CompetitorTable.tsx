import React from 'react';
import type { CompetitorData, Source } from '../types';
import { Citations } from './Citations';

// Same order as the strength chart above, strongest first
export const CompetitorTable: React.FC<{ competitors: CompetitorData[]; sources: Source[] }> = ({ competitors, sources }) => (
  <div className="table-wrap">
    <table>
      <thead>
        <tr>
          <th scope="col">Company</th>
          <th scope="col">Pricing</th>
          <th scope="col">Target audience</th>
          <th scope="col">Value proposition</th>
          <th scope="col">Strength</th>
        </tr>
      </thead>
      <tbody>
        {[...competitors].sort((a, b) => b.market_strength_score - a.market_strength_score).map(c => (
          <tr key={c.name}>
            <td className="name">
              {c.name}
              <Citations ids={c.source_ids} sources={sources} />
            </td>
            <td>{c.pricing_model}</td>
            <td>{c.target_audience}</td>
            <td>{c.core_value_proposition}</td>
            <td className="num">{c.market_strength_score}/10</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
