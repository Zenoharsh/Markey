import React from 'react';
import type { Source } from '../types';
import { hostname } from '../lib/format';

interface CitationsProps {
  ids: number[];
  sources: Source[];
}

// Numbered markers after a statement; hovering or focusing one shows the source it points at
export const Citations: React.FC<CitationsProps> = ({ ids, sources }) => (
  <>
    {ids.map(id => {
      const source = sources.find(s => s.id === id);
      if (!source) return null;
      return (
        <span className="cite" key={id}>
          <a href={source.url} target="_blank" rel="noopener noreferrer" aria-label={`Source ${id}: ${source.title}`}>
            {id}
          </a>
          <span className="cite-card" role="tooltip">
            {source.title}
            <span>{hostname(source.url)}</span>
          </span>
        </span>
      );
    })}
  </>
);
