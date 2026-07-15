import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Loader2,
  FileText,
  Database,
  LayoutDashboard,
  BarChart3,
  ScrollText,
  X,
} from 'lucide-react';
import { globalSearch, type SearchResult, type SearchResults } from '@/lib/api';

const categoryConfig = {
  pipelines: { icon: FileText, label: 'Pipelines', color: 'text-blue-500' },
  connections: { icon: Database, label: 'Connections', color: 'text-green-500' },
  dashboards: { icon: LayoutDashboard, label: 'Dashboards', color: 'text-purple-500' },
  metrics: { icon: BarChart3, label: 'Metrics', color: 'text-orange-500' },
  logs: { icon: ScrollText, label: 'Logs', color: 'text-slate-500' },
};

export function UniversalSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults>({
    pipelines: [],
    connections: [],
    dashboards: [],
    metrics: [],
    logs: [],
  });
  const [isSearching, setIsSearching] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsFocused(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setIsFocused(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults({ pipelines: [], connections: [], dashboards: [], metrics: [], logs: [] });
      return;
    }

    setIsSearching(true);
    try {
      const searchResults = await globalSearch(searchQuery);
      setResults(searchResults);
      setSelectedIndex(0);
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setIsSearching(false);
    }
  }, []);

  useEffect(() => {
    const debounce = setTimeout(() => {
      performSearch(query);
    }, 300);
    return () => clearTimeout(debounce);
  }, [query, performSearch]);

  const allResults = [
    ...results.pipelines,
    ...results.connections,
    ...results.dashboards,
    ...results.metrics,
    ...results.logs,
  ];

  const totalResults = allResults.length;

  const handleSelect = (result: SearchResult) => {
    navigate(result.path);
    setQuery('');
    setIsFocused(false);
    setResults({ pipelines: [], connections: [], dashboards: [], metrics: [], logs: [] });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, totalResults - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && allResults[selectedIndex]) {
      e.preventDefault();
      handleSelect(allResults[selectedIndex]);
    } else if (e.key === 'Escape') {
      setIsFocused(false);
      inputRef.current?.blur();
    }
  };

  const renderCategory = (category: keyof typeof categoryConfig, items: SearchResult[]) => {
    if (items.length === 0) return null;

    const config = categoryConfig[category];
    const Icon = config.icon;

    return (
      <div className="py-1">
        <div className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
          <Icon className={`w-3 h-3 ${config.color}`} />
          {config.label}
        </div>
        {items.map((item, idx) => {
          const globalIdx = allResults.indexOf(item);
          const isSelected = globalIdx === selectedIndex;
          return (
            <button
              key={`${category}-${item.id}-${idx}`}
              onClick={() => handleSelect(item)}
              onMouseEnter={() => setSelectedIndex(globalIdx)}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors ${
                isSelected ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/50'
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-medium truncate">{item.title}</div>
                {item.subtitle && (
                  <div className="text-[10px] text-muted-foreground truncate">
                    {item.subtitle}
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    );
  };

  const showDropdown = isFocused && query.trim() !== '';

  return (
    <div ref={containerRef} className="relative">
      <div 
        className={`cmdk-trigger group flex h-8 w-[300px] xl:w-[380px] items-center gap-2 rounded-md px-2.5 text-left transition-shadow ${
          isFocused ? 'ring-2 ring-primary/50' : ''
        }`}
      >
        {isSearching ? (
          <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
        ) : (
          <Search className="w-4 h-4 text-muted-foreground" />
        )}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search pipelines, connections..."
          className="flex-1 bg-transparent text-[12px] outline-none placeholder:text-muted-foreground"
        />
        {query && (
          <button 
            onClick={(e) => {
              e.preventDefault();
              setQuery('');
              inputRef.current?.focus();
            }} 
            className="p-0.5 rounded hover:bg-muted"
          >
            <X className="w-3 h-3 text-muted-foreground" />
          </button>
        )}
        <kbd className="hidden sm:inline-flex h-4 items-center rounded border border-border bg-muted px-1 text-[9px] text-muted-foreground">
          ⌘K
        </kbd>
      </div>

      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-background border border-border rounded-md shadow-lg overflow-hidden z-50 max-h-[400px] overflow-y-auto">
          {isSearching ? (
            <div className="px-4 py-6 text-center text-xs text-muted-foreground">
              <Loader2 className="w-5 h-5 mx-auto mb-2 animate-spin" />
              Searching...
            </div>
          ) : totalResults === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-muted-foreground">
              <Search className="w-6 h-6 mx-auto mb-2 opacity-30" />
              <p>No results for "{query}"</p>
            </div>
          ) : (
            <>
              <div className="px-3 py-1.5 text-[10px] text-muted-foreground border-b border-border bg-muted/50">
                {totalResults} result{totalResults !== 1 ? 's' : ''}
              </div>
              {renderCategory('pipelines', results.pipelines)}
              {renderCategory('connections', results.connections)}
              {renderCategory('dashboards', results.dashboards)}
              {renderCategory('metrics', results.metrics)}
              {renderCategory('logs', results.logs)}
            </>
          )}
        </div>
      )}
    </div>
  );
}
