import React from 'react';
import type { Source } from '../types';
import { formatDate, hostname } from '../lib/format';

export const SourcesList: React.FC<{ sources: Source[] }> = ({ sources }) => (
  <ol className="sources">
    {sources.map(source => (
      <li key={source.id} id={`source-${source.id}`} className="source">
        <span className="source-id">{source.id}</span>
        <div className="source-body">
          <a href={source.url} target="_blank" rel="noopener noreferrer">
            {source.title}
          </a>
          <div className="meta">
            {hostname(source.url)}
            {source.retrieved_at && ` · read ${formatDate(source.retrieved_at)}`}
          </div>
        </div>
      </li>
    ))}
  </ol>
);
