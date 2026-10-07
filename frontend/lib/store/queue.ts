import { create } from 'zustand';
import {
  getQueue,
  prioritizeDownload,
  pauseAllDownloads,
  resumeAllDownloads,
  pauseDownload,
  resumeDownload,
  cancelDownload,
  retryDownload,
  QueueSnapshot,
  QueueEntry,
  DownloadActionResult,
} from '../api/queue';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface QueueState {
  snapshot: QueueSnapshot | null;
  isLoading: boolean;
  isPausingAll: boolean;
  isResumingAll: boolean;
  wsConnected: boolean;
  toasts: Toast[];

  fetchQueue: () => Promise<void>;
  prioritize: (id: string) => Promise<QueueEntry | null>;
  pauseAll: () => Promise<void>;
  resumeAll: () => Promise<void>;
  pause: (id: string) => Promise<DownloadActionResult | null>;
  resume: (id: string) => Promise<DownloadActionResult | null>;
  cancel: (id: string) => Promise<DownloadActionResult | null>;
  retry: (id: string) => Promise<DownloadActionResult | null>;
  setWsConnected: (connected: boolean) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useQueueStore = create<QueueState>((set, get) => ({
  snapshot: null,
  isLoading: false,
  isPausingAll: false,
  isResumingAll: false,
  wsConnected: false,
  toasts: [],

  fetchQueue: async () => {
    set({ isLoading: true });
    try {
      const snapshot = await getQueue();
      set({ snapshot });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load queue', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isLoading: false });
    }
  },

  prioritize: async (id) => {
    try {
      const entry = await prioritizeDownload(id);
      const toast = { id: generateId(), message: 'Download prioritized', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
      return entry;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to prioritize download', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      return null;
    }
  },

  pauseAll: async () => {
    set({ isPausingAll: true });
    try {
      const result = await pauseAllDownloads();
      const toast = { id: generateId(), message: `Paused ${result.affected} download(s)`, type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to pause all downloads', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isPausingAll: false });
    }
  },

  resumeAll: async () => {
    set({ isResumingAll: true });
    try {
      const result = await resumeAllDownloads();
      const toast = { id: generateId(), message: `Resumed ${result.affected} download(s)`, type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to resume all downloads', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isResumingAll: false });
    }
  },

  pause: async (id) => {
    try {
      const result = await pauseDownload(id);
      const toast = { id: generateId(), message: 'Download paused', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
      return result;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to pause download', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      return null;
    }
  },

  resume: async (id) => {
    try {
      const result = await resumeDownload(id);
      const toast = { id: generateId(), message: 'Download resumed', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
      return result;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to resume download', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      return null;
    }
  },

  cancel: async (id) => {
    try {
      const result = await cancelDownload(id);
      const toast = { id: generateId(), message: 'Download cancelled', type: 'info' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
      return result;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to cancel download', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      return null;
    }
  },

  retry: async (id) => {
    try {
      const result = await retryDownload(id);
      const toast = { id: generateId(), message: 'Download retried', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchQueue();
      return result;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to retry download', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      return null;
    }
  },

  setWsConnected: (connected) => set({ wsConnected: connected }),

  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));

