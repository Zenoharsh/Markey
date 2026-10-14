import React from 'react';
import { Card } from './Card';
import type { Source } from '../types';

const hostname = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
};

export const SourcesList: React.FC<{ sources: Source[] }> = ({ sources }) => (
  <Card style={{ margin: 0, padding: '24px' }}>
    <h3 style={{ fontSize: '1.2rem', marginBottom: '12px', color: '#4a5568' }}>Sources ({sources.length})</h3>
    <ol style={{ paddingLeft: '24px', lineHeight: '1.6', color: '#4a5568', fontSize: '0.9rem' }}>
      {sources.map(source => (
        <li key={source.id} value={source.id} style={{ marginBottom: '6px' }}>
          <a href={source.url} target="_blank" rel="noopener noreferrer" style={{ color: '#2d3748' }}>
            {source.title}
          </a>
          <span style={{ color: '#718096' }}> · {hostname(source.url)}</span>
          {source.retrieved_at && (
            <span style={{ color: '#a0aec0' }}> · read {source.retrieved_at.slice(0, 10)}</span>
          )}
        </li>
      ))}
    </ol>
  </Card>
);
