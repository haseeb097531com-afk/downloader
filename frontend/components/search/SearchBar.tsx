'use client';

import { useState, useEffect, useCallback } from 'react';
import { Search, Sparkles, X, Bookmark } from 'lucide-react';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
}

export function SearchBar({ value, onChange, onSave }: SearchBarProps) {
  const [localValue, setLocalValue] = useState(value);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localValue !== value) {
        onChange(localValue);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [localValue, value, onChange]);

  const handleClear = useCallback(() => {
    setLocalValue('');
    onChange('');
  }, [onChange]);

  return (
    <div className="relative w-full">
      <div className="glass-card rounded-xl overflow-hidden">
        <div className="flex items-center">
          <div className="pl-5 pr-3 text-text-muted">
            <Search className="w-5 h-5" />
          </div>
          <input
            type="text"
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            placeholder="Search media..."
            className="flex-1 bg-transparent py-4 pr-4 text-text-primary placeholder:text-text-muted focus:outline-none"
          />
          {localValue && (
            <button
              onClick={handleClear}
              className="px-3 text-text-muted hover:text-text-primary transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
          {onSave && (
            <button
              onClick={onSave}
              className="mr-3 p-2 rounded-lg bg-bg-tertiary text-text-secondary hover:text-accent-primary transition-colors"
              title="Save this search"
            >
              <Bookmark className="w-5 h-5" />
            </button>
          )}
          <div className="pr-5 pl-3 text-accent-primary">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>
      </div>
    </div>
  );
}
