import { create } from 'zustand';
import {
  getLibrary,
  getLibraryStats,
  getCategories,
  renameLibraryItem,
  deleteLibraryItem,
  openLibraryFolder,
  getUntrackedFiles,
  importUntrackedFiles,
  LibraryItem,
  LibraryStats,
  CategoryCount,
  UntrackedFile,
  ImportResult,
} from '../api/library';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface LibraryState {
  items: LibraryItem[];
  stats: LibraryStats | null;
  categories: CategoryCount[];
  untracked: UntrackedFile[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  platform: string;
  category: string;
  search: string;
  isLoading: boolean;
  isStatsLoading: boolean;
  isUntrackedLoading: boolean;
  isCategoriesLoading: boolean;
  toasts: Toast[];
  selectedItem: LibraryItem | null;

  fetchLibrary: (page?: number, platform?: string, search?: string, category?: string) => Promise<void>;
  fetchStats: () => Promise<void>;
  fetchUntracked: () => Promise<void>;
  fetchCategories: () => Promise<void>;
  importUntracked: (paths: string[]) => Promise<ImportResult>;
  renameItem: (id: string, newName: string) => Promise<void>;
  deleteItem: (id: string) => Promise<void>;
  openFolder: (id: string) => Promise<void>;
  setPage: (page: number) => void;
  setPlatform: (platform: string) => void;
  setCategory: (category: string) => void;
  setSearch: (search: string) => void;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
  setSelectedItem: (item: LibraryItem | null) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useLibraryStore = create<LibraryState>((set, get) => ({
  items: [],
  stats: null,
  categories: [],
  untracked: [],
  page: 1,
  limit: 24,
  total: 0,
  totalPages: 0,
  hasNext: false,
  platform: '',
  category: '',
  search: '',
  isLoading: false,
  isStatsLoading: false,
  isUntrackedLoading: false,
  isCategoriesLoading: false,
  toasts: [],
  selectedItem: null,

  fetchLibrary: async (page = 1, platform, search, category) => {
    const p = platform ?? get().platform;
    const s = search ?? get().search;
    const c = category ?? get().category;
    set({ isLoading: true });
    try {
      const result = await getLibrary(page, get().limit, p || undefined, s || undefined, c || undefined);
      set({
        items: result.items,
        page: result.page,
        total: result.total,
        totalPages: result.total_pages,
        hasNext: result.has_next,
        platform: p,
        category: c,
        search: s,
      });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load library', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isLoading: false });
    }
  },

  fetchStats: async () => {
    set({ isStatsLoading: true });
    try {
      const stats = await getLibraryStats();
      set({ stats });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load stats', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isStatsLoading: false });
    }
  },

  fetchUntracked: async () => {
    set({ isUntrackedLoading: true });
    try {
      const untracked = await getUntrackedFiles();
      set({ untracked });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to scan for untracked files', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isUntrackedLoading: false });
    }
  },

  fetchCategories: async () => {
    set({ isCategoriesLoading: true });
    try {
      const categories = await getCategories();
      set({ categories });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load categories', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isCategoriesLoading: false });
    }
  },

  importUntracked: async (paths) => {
    try {
      const result = await importUntrackedFiles(paths);
      if (result.imported > 0) {
        const successToast = { id: generateId(), message: `Imported ${result.imported} file(s)`, type: 'success' as const };
        set((state) => ({ toasts: [...state.toasts, successToast] }));
        setTimeout(() => get().dismissToast(successToast.id), 4000);
        get().fetchLibrary(get().page, get().platform, get().search);
        get().fetchStats();
        get().fetchUntracked();
        get().fetchCategories();
      }
      if (result.skipped > 0) {
        const infoToast = { id: generateId(), message: `Skipped ${result.skipped} file(s)`, type: 'info' as const };
        set((state) => ({ toasts: [...state.toasts, infoToast] }));
        setTimeout(() => get().dismissToast(infoToast.id), 4000);
      }
      return result;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to import files', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  renameItem: async (id, newName) => {
    try {
      const updated = await renameLibraryItem(id, newName);
      set((state) => ({
        items: state.items.map((item) => (item.id === id ? updated : item)),
      }));
      const toast = { id: generateId(), message: 'File renamed successfully', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to rename file', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  deleteItem: async (id) => {
    try {
      await deleteLibraryItem(id);
      set((state) => ({
        items: state.items.filter((item) => item.id !== id),
        total: state.total - 1,
      }));
      const toast = { id: generateId(), message: 'File deleted', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to delete file', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  openFolder: async (id) => {
    try {
      await openLibraryFolder(id);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to open folder', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  setPage: (page) => {
    set({ page });
    get().fetchLibrary(page);
  },

  setPlatform: (platform) => {
    set({ platform, page: 1 });
    get().fetchLibrary(1, platform, get().search);
  },

  setCategory: (category) => {
    set({ category, page: 1 });
    get().fetchLibrary(1, get().platform, get().search, category);
  },

  setSearch: (search) => {
    set({ search, page: 1 });
  },

  addToast: (message: string, type: Toast['type']) => {
    const toast: Toast = { id: generateId(), message, type };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    setTimeout(() => get().dismissToast(toast.id), 4000);
  },

  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },

  setSelectedItem: (item) => set({ selectedItem: item }),
}));

