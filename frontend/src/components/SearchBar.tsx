import React, { useState } from 'react';
import { Search } from 'lucide-react';

interface SearchBarProps {
  onSearch: (query: string) => void;
  disabled?: boolean;
}

const SUGGESTIONS = ['Electric scooters', 'AI note-taking apps', 'Plant-based protein', 'Cloud gaming', 'Pet insurance'];

// Spotlight-style search field with example topics underneath
export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, disabled }) => {
  const [query, setQuery] = useState('');
  const trimmed = query.trim();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (trimmed.length >= 2) onSearch(trimmed);
  };

  return (
    <>
      <form className="spotlight glass" onSubmit={handleSubmit} role="search">
        <Search size={20} color="var(--text-muted)" aria-hidden="true" />
        <input
          type="text"
          placeholder="Any market or product"
          aria-label="Topic to research"
          value={query}
          maxLength={300}
          onChange={e => setQuery(e.target.value)}
          disabled={disabled}
          autoFocus
        />
        <button type="submit" className="button button-primary" disabled={disabled || trimmed.length < 2}>
          Research
        </button>
      </form>
      <div className="suggestions">
        {SUGGESTIONS.map(topic => (
          <button key={topic} type="button" className="chip" onClick={() => onSearch(topic)} disabled={disabled}>
            {topic}
          </button>
        ))}
      </div>
    </>
  );
};
