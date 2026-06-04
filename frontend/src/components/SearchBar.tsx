import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isLoading }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '24px', alignItems: 'center', width: '100%' }}>
      <input
        type="text"
        className="neu-pressed"
        placeholder="Enter industry (e.g., Cloud Computing)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={isLoading}
        style={{
          flex: 1,
          padding: '16px 24px',
          border: 'none',
          outline: 'none',
          fontSize: '1.1rem',
          color: '#4a5568',
        }}
      />
      <button 
        type="submit" 
        disabled={isLoading || !query.trim()}
        className="neu-button-primary"
        style={{ 
          padding: '16px 32px',
          border: 'none',
          cursor: isLoading ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontWeight: 'bold',
          fontSize: '1.1rem'
        }}
      >
        {isLoading ? <Loader2 className="animate-spin" /> : <Search />}
        {isLoading ? 'Researching...' : 'Analyze'}
      </button>
    </form>
  );
};
