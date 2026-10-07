import { LibraryItem } from './library';

export interface SearchFilters {
  platforms?: string[];
  categories?: string[];
  quality?: string;
  date_from?: string;
  date_to?: string;
  size_min_mb?: number;
  size_max_mb?: number;
  watermark_free?: boolean;
  cloud_backed?: boolean;
  include_quarantined?: boolean;
}

export interface SearchSort {
  field: 'date' | 'size' | 'title' | 'platform';
  direction: 'asc' | 'desc';
}

export interface SearchRequest {
  q: string;
  filters?: SearchFilters;
  sort?: SearchSort;
  page: number;
  limit: number;
}

export interface SearchResultItem extends LibraryItem {
  id: string;
}

export interface FacetBucket {
  value: string;
  count: number;
}

export interface SearchFacets {
  platforms: FacetBucket[];
  categories: FacetBucket[];
}

export interface SearchResponse {
  items: SearchResultItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  facets: SearchFacets;
}

export interface SavedSearch {
  id: string;
  name: string;
  query: string;
  filters: SearchFilters | null;
  sort: SearchSort | null;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function searchMedia(payload: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function getSavedSearches(): Promise<SavedSearch[]> {
  const res = await fetch(`${API_BASE}/saved-searches`);
  if (!res.ok) throw new Error('Failed to fetch saved searches');
  return res.json();
}

export async function createSavedSearch(payload: { name: string; query: string; filters?: SearchFilters; sort?: SearchSort }): Promise<SavedSearch> {
  const res = await fetch(`${API_BASE}/saved-searches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to save search');
  return res.json();
}

export async function deleteSavedSearch(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/saved-searches/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete saved search');
}
