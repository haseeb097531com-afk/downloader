import { create } from 'zustand';
import {
  checkDedupUrl,
  startDedupScan,
  getDedupReport,
  dedupCleanup,
  DuplicateMatch,
  DedupReportResponse,
} from '../api/dedup';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface DedupState {
  duplicateMatches: DuplicateMatch[] | null;
  report: DedupReportResponse | null;
  scanning: boolean;
  selectedDeleteIds: Set<string>;
  cleanupLoading: boolean;
  toasts: Toast[];

  checkUrl: (url: string) => Promise<DuplicateMatch[] | null>;
  startScan: () => Promise<void>;
  fetchReport: () => Promise<void>;
  toggleDeleteSelection: (id: string) => void;
  setSelectedDeleteIds: (ids: Set<string>) => void;
  runCleanup: (deleteIds: string[]) => Promise<{ deleted_count: number } | null>;
  clearReport: () => void;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useDedupStore = create<DedupState>((set, get) => ({
  duplicateMatches: null,
  report: null,
  scanning: false,
  selectedDeleteIds: new Set<string>(),
  cleanupLoading: false,
  toasts: [],

  checkUrl: async (url) => {
    try {
      const result = await checkDedupUrl(url);
      if (result.matches.length > 0) {
        set({ duplicateMatches: result.matches });
        return result.matches;
      }
      set({ duplicateMatches: null });
      return null;
    } catch (e) {
      console.error(e);
      return null;
    }
  },

  startScan: async () => {
    set({ scanning: true, report: null, selectedDeleteIds: new Set() });
    try {
      await startDedupScan();
      get().addToast('Scanning library for duplicates...', 'info');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to start duplicate scan', 'error');
      set({ scanning: false });
    }
  },

  fetchReport: async () => {
    try {
      const report = await getDedupReport();
      set({ report });
      if (report.groups.length === 0) {
        set({ scanning: false });
      }
    } catch (e) {
      console.error(e);
      get().addToast('Failed to fetch duplicate report', 'error');
      set({ scanning: false });
    }
  },

  toggleDeleteSelection: (id) => {
    const next = new Set(get().selectedDeleteIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    set({ selectedDeleteIds: next });
  },

  setSelectedDeleteIds: (ids) => set({ selectedDeleteIds: ids }),

  runCleanup: async (deleteIds) => {
    if (deleteIds.length === 0) return null;
    set({ cleanupLoading: true });
    try {
      const result = await dedupCleanup(deleteIds);
      get().addToast(`Deleted ${result.deleted_count} duplicate(s)`, 'success');
      set({ cleanupLoading: false, selectedDeleteIds: new Set() });
      return result;
    } catch (e) {
      console.error(e);
      get().addToast('Failed to delete duplicates', 'error');
      set({ cleanupLoading: false });
      return null;
    }
  },

  clearReport: () => {
    set({ report: null, selectedDeleteIds: new Set() });
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

