'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, X } from 'lucide-react';
import { SearchFilters, SearchSort, FacetBucket } from '@/lib/api/search';
import { QUALITY_PRESETS } from '@/lib/constants/quality-presets';

interface FilterPanelProps {
  filters: SearchFilters;
  facets: { platforms: FacetBucket[]; categories: FacetBucket[] };
  sort: SearchSort;
  onFiltersChange: (filters: SearchFilters) => void;
  onSortChange: (sort: SearchSort) => void;
  onClose?: () => void;
}

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'bg-platform-youtube',
  tiktok: 'bg-platform-tiktok',
  instagram: 'bg-platform-instagram',
  facebook: 'bg-platform-facebook',
  twitter: 'bg-platform-twitter',
  whatsapp: 'bg-platform-whatsapp',
};

export function FilterPanel({ filters, facets, sort, onFiltersChange, onSortChange, onClose }: FilterPanelProps) {
  const [isOpen, setIsOpen] = useState(true);

  const togglePlatform = (platform: string) => {
    const current = filters.platforms || [];
    const next = current.includes(platform)
      ? current.filter((p) => p !== platform)
      : [...current, platform];
    onFiltersChange({ ...filters, platforms: next });
  };

  const toggleCategory = (category: string) => {
    const current = filters.categories || [];
    const next = current.includes(category)
      ? current.filter((c) => c !== category)
      : [...current, category];
    onFiltersChange({ ...filters, categories: next });
  };

  const update = (patch: Partial<SearchFilters>) => {
    onFiltersChange({ ...filters, ...patch });
  };

  const clearAll = () => {
    onFiltersChange({});
  };

  const activeCount = [
    filters.platforms?.length,
    filters.categories?.length,
    filters.quality ? 1 : 0,
    filters.date_from || filters.date_to ? 1 : 0,
    filters.size_min_mb || filters.size_max_mb ? 1 : 0,
    filters.watermark_free ? 1 : 0,
    filters.cloud_backed ? 1 : 0,
    filters.include_quarantined ? 1 : 0,
  ].filter(Boolean).length;

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-2">
          <h3 className="text-text-primary font-semibold">Filters</h3>
          {activeCount > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-accent-primary/20 text-accent-primary text-xs font-medium">
              {activeCount} active
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeCount > 0 && (
            <button onClick={clearAll} className="text-xs text-text-secondary hover:text-text-primary">
              Clear all
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="lg:hidden text-text-secondary hover:text-text-primary">
              <X className="w-5 h-5" />
            </button>
          )}
          <button onClick={() => setIsOpen(!isOpen)} className="text-text-secondary hover:text-text-primary">
            {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="px-4 pb-4 space-y-6">
          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Platform</label>
            <div className="flex flex-wrap gap-2">
              {facets.platforms.map((facet) => {
                const isActive = (filters.platforms || []).includes(facet.value);
                return (
                  <button
                    key={facet.value}
                    onClick={() => togglePlatform(facet.value)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? `${PLATFORM_COLORS[facet.value] || 'bg-accent-primary'} text-white`
                        : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {facet.value} ({facet.count})
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Category</label>
            <div className="flex flex-wrap gap-2">
              {facets.categories.map((facet) => {
                const isActive = (filters.categories || []).includes(facet.value);
                return (
                  <button
                    key={facet.value}
                    onClick={() => toggleCategory(facet.value)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-accent-primary text-white'
                        : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {facet.value || 'Uncategorized'} ({facet.count})
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Quality</label>
            <select
              value={filters.quality || ''}
              onChange={(e) => update({ quality: e.target.value || undefined })}
              className="w-full px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
            >
              <option value="">Any</option>
              {QUALITY_PRESETS.map(q => (
                <option key={q.value} value={q.value}>{q.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Date Range</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={filters.date_from || ''}
                onChange={(e) => update({ date_from: e.target.value || undefined })}
                className="flex-1 px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary"
              />
              <input
                type="date"
                value={filters.date_to || ''}
                onChange={(e) => update({ date_to: e.target.value || undefined })}
                className="flex-1 px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Size Range (MB)</label>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Min"
                value={filters.size_min_mb ?? ''}
                onChange={(e) => update({ size_min_mb: e.target.value ? Number(e.target.value) : undefined })}
                className="flex-1 px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary"
              />
              <input
                type="number"
                placeholder="Max"
                value={filters.size_max_mb ?? ''}
                onChange={(e) => update({ size_max_mb: e.target.value ? Number(e.target.value) : undefined })}
                className="flex-1 px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary"
              />
            </div>
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.watermark_free || false}
                onChange={(e) => update({ watermark_free: e.target.checked || undefined })}
                className="w-4 h-4 rounded border-border bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
              />
              <span className="text-text-primary text-sm">Watermark-free only</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.cloud_backed || false}
                onChange={(e) => update({ cloud_backed: e.target.checked || undefined })}
                className="w-4 h-4 rounded border-border bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
              />
              <span className="text-text-primary text-sm">Cloud-backed only</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.include_quarantined || false}
                onChange={(e) => update({ include_quarantined: e.target.checked || undefined })}
                className="w-4 h-4 rounded border-border bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
              />
              <span className="text-text-primary text-sm">Include quarantined</span>
            </label>
          </div>

          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Sort by</label>
            <select
              value={`${sort.field}-${sort.direction}`}
              onChange={(e) => {
                const [field, direction] = e.target.value.split('-');
                onSortChange({ field: field as SearchSort['field'], direction: direction as SearchSort['direction'] });
              }}
              className="w-full px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary"
            >
              <option value="date-desc">Date (newest)</option>
              <option value="date-asc">Date (oldest)</option>
              <option value="size-desc">Size (largest)</option>
              <option value="size-asc">Size (smallest)</option>
              <option value="title-asc">Title (A-Z)</option>
              <option value="title-desc">Title (Z-A)</option>
              <option value="platform-asc">Platform (A-Z)</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

