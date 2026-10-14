import React from 'react';
import type { Source } from '../types';

interface CitationsProps {
  ids: number[];
  sources: Source[];
}

// Numbered links after a statement, pointing at the sources that support it
export const Citations: React.FC<CitationsProps> = ({ ids, sources }) => (
  <>
    {ids.map(id => {
      const source = sources.find(s => s.id === id);
      if (!source) return null;
      return (
        <a
          key={id}
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          title={source.title}
          style={{ fontSize: '0.75em', verticalAlign: 'super', marginLeft: '2px', color: '#3b82f6', textDecoration: 'none' }}
        >
          [{id}]
        </a>
      );
    })}
  </>
);
