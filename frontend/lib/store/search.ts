import { create } from 'zustand';
import {
  searchMedia,
  createSavedSearch,
  deleteSavedSearch,
  getSavedSearches,
  SearchFilters,
  SearchResponse,
  SearchSort,
  SavedSearch,
} from '../api/search';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface SearchState {
  query: string;
  filters: SearchFilters;
  sort: SearchSort;
  page: number;
  limit: number;
  results: SearchResponse | null;
  savedSearches: SavedSearch[];
  isLoading: boolean;
  isSavingSearch: boolean;
  toasts: Toast[];

  setQuery: (query: string) => void;
  setFilters: (filters: SearchFilters) => void;
  setSort: (sort: SearchSort) => void;
  setPage: (page: number) => void;
  runSearch: () => Promise<void>;
  saveSearch: (name: string) => Promise<void>;
  removeSavedSearch: (id: string) => Promise<void>;
  loadSavedSearches: () => Promise<void>;
  applySavedSearch: (saved: SavedSearch) => void;
  dismissToast: (id: string) => void;
  addToast: (message: string, type: Toast['type']) => void;
}

const DEFAULT_SORT: SearchSort = { field: 'date', direction: 'desc' };
const DEFAULT_FILTERS: SearchFilters = {};

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useSearchStore = create<SearchState>((set, get) => ({
  query: '',
  filters: DEFAULT_FILTERS,
  sort: DEFAULT_SORT,
  page: 1,
  limit: 20,
  results: null,
  savedSearches: [],
  isLoading: false,
  isSavingSearch: false,
  toasts: [],

  setQuery: (query) => {
    set({ query, page: 1 });
    get().runSearch();
  },

  setFilters: (filters) => {
    set({ filters, page: 1 });
    get().runSearch();
  },

  setSort: (sort) => {
    set({ sort, page: 1 });
    get().runSearch();
  },

  setPage: (page) => {
    set({ page });
    get().runSearch();
  },

  runSearch: async () => {
    const { query, filters, sort, page, limit } = get();
    if (!query.trim()) {
      set({ results: null });
      return;
    }
    set({ isLoading: true });
    try {
      const response = await searchMedia({ q: query, filters, sort, page, limit });
      set({ results: response });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Search failed', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isLoading: false });
    }
  },

  saveSearch: async (name) => {
    const { query, filters, sort } = get();
    set({ isSavingSearch: true });
    try {
      const saved = await createSavedSearch({ name, query, filters, sort });
      set((state) => ({ savedSearches: [saved, ...state.savedSearches] }));
      get().addToast('Search saved', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to save search', 'error');
    } finally {
      set({ isSavingSearch: false });
    }
  },

  removeSavedSearch: async (id) => {
    try {
      await deleteSavedSearch(id);
      set((state) => ({ savedSearches: state.savedSearches.filter((s) => s.id !== id) }));
      get().addToast('Saved search removed', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to remove saved search', 'error');
    }
  },

  loadSavedSearches: async () => {
    try {
      const searches = await getSavedSearches();
      set({ savedSearches: searches });
    } catch (e) {
      console.error(e);
    }
  },

  applySavedSearch: (saved) => {
    set({
      query: saved.query,
      filters: saved.filters || DEFAULT_FILTERS,
      sort: saved.sort || DEFAULT_SORT,
      page: 1,
    });
    get().runSearch();
  },

  addToast: (message, type) => {
    const toast = { id: generateId(), message, type };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    setTimeout(() => get().dismissToast(toast.id), 4000);
  },

  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));
