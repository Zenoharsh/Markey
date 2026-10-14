import React from 'react';
import type { ForceAssessment, Intensity, Source } from '../types';
import { Citations } from './Citations';

const LEVEL: Record<Intensity, number> = { low: 1, medium: 2, high: 3 };
const ORDER = ['Competitive rivalry', 'Threat of new entrants', 'Buyer power', 'Supplier power', 'Threat of substitutes'];

// Porter's five forces: a three-step meter plus the word, so intensity never depends on the meter alone
export const ForcesPanel: React.FC<{ forces: ForceAssessment[]; sources: Source[] }> = ({ forces, sources }) => (
  <ul className="forces">
    {[...forces]
      .sort((a, b) => ORDER.indexOf(a.force) - ORDER.indexOf(b.force))
      .map(f => (
        <li key={f.force} className="force">
          <div className="force-head">
            <span className="force-name">{f.force}</span>
            <span className="force-level">
              <span className="meter" aria-hidden="true">
                {[1, 2, 3].map(step => (
                  <i key={step} className={step <= LEVEL[f.intensity] ? 'on' : ''} />
                ))}
              </span>
              <span className="force-word">{f.intensity}</span>
            </span>
          </div>
          <p>
            {f.rationale}
            <Citations ids={f.source_ids} sources={sources} />
          </p>
        </li>
      ))}
  </ul>
);
