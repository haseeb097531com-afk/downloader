import { create } from 'zustand';
import {
  getDesktopStatus,
  startDesktopServices,
  stopDesktopServices,
  getPendingLinks,
  dismissPendingLink,
  downloadPendingLink,
  DesktopStatus,
  PendingLink,
} from '../api/desktop';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface DesktopState {
  status: DesktopStatus | null;
  pendingQueue: PendingLink[];
  activePending: PendingLink | null;
  modalOpen: boolean;
  toasts: Toast[];
  wsConnected: boolean;
  isStartingClipboard: boolean;
  isStoppingClipboard: boolean;
  isStartingTray: boolean;
  isStoppingTray: boolean;
  isDownloading: boolean;

  fetchStatus: () => Promise<void>;
  startServices: (type: 'clipboard' | 'tray') => Promise<void>;
  stopServices: (type: 'clipboard' | 'tray') => Promise<void>;
  subscribeClipboardWS: () => () => void;
  fetchPending: () => Promise<void>;
  nextPending: () => void;
  downloadActive: () => Promise<void>;
  dismissActive: () => Promise<void>;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useDesktopStore = create<DesktopState>((set, get) => ({
  status: null,
  pendingQueue: [],
  activePending: null,
  modalOpen: false,
  toasts: [],
  wsConnected: false,
  isStartingClipboard: false,
  isStoppingClipboard: false,
  isStartingTray: false,
  isStoppingTray: false,
  isDownloading: false,

  fetchStatus: async () => {
    try {
      const status = await getDesktopStatus();
      set({ status });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load desktop status', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    }
  },

  startServices: async (type) => {
    if (type === 'clipboard') set({ isStartingClipboard: true });
    else set({ isStartingTray: true });

    try {
      const options: { clipboard?: boolean; tray?: boolean } = {};
      if (type === 'clipboard') options.clipboard = true;
      else options.tray = true;
      await startDesktopServices(options);
      const toast = {
        id: generateId(),
        message: `${type === 'clipboard' ? 'Clipboard monitor' : 'System tray'} started`,
        type: 'success' as const,
      };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchStatus();
    } catch (e) {
      console.error(e);
      const toast = {
        id: generateId(),
        message: `Failed to start ${type === 'clipboard' ? 'clipboard monitor' : 'system tray'}`,
        type: 'error' as const,
      };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      if (type === 'clipboard') set({ isStartingClipboard: false });
      else set({ isStartingTray: false });
    }
  },

  stopServices: async (type) => {
    if (type === 'clipboard') set({ isStoppingClipboard: true });
    else set({ isStoppingTray: true });

    try {
      await stopDesktopServices();
      const toast = {
        id: generateId(),
        message: `${type === 'clipboard' ? 'Clipboard monitor' : 'System tray'} stopped`,
        type: 'success' as const,
      };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().fetchStatus();
    } catch (e) {
      console.error(e);
      const toast = {
        id: generateId(),
        message: `Failed to stop ${type === 'clipboard' ? 'clipboard monitor' : 'system tray'}`,
        type: 'error' as const,
      };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      if (type === 'clipboard') set({ isStoppingClipboard: false });
      else set({ isStoppingTray: false });
    }
  },

  subscribeClipboardWS: () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/';
    let wsUrl: string;
    try {
      const url = new URL(apiUrl);
      const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${url.host}/ws/clipboard`;
    } catch {
      wsUrl = '/ws/clipboard';
    }

    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        ws.onopen = () => set({ wsConnected: true });
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.url) {
              const pending: PendingLink = {
                id: data.id || generateId(),
                url: data.url,
                platform: data.platform || 'unknown',
                detected_at: data.detected_at || new Date().toISOString(),
              };
              set((state) => ({
                pendingQueue: [...state.pendingQueue, pending],
                activePending: state.activePending || pending,
                modalOpen: true,
              }));
            }
          } catch (e) {
            console.error('Failed to parse WS message', e);
          }
        };
        ws.onclose = () => {
          set({ wsConnected: false });
          reconnectTimeout = setTimeout(connect, 3000);
        };
        ws.onerror = () => {
          ws?.close();
        };
      } catch (e) {
        console.error('Failed to connect WS', e);
        reconnectTimeout = setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      ws?.close();
    };
  },

  fetchPending: async () => {
    try {
      const pending = await getPendingLinks();
      if (pending.length > 0) {
        set({
          pendingQueue: pending,
          activePending: pending[0],
          modalOpen: true,
        });
      }
    } catch (e) {
      console.error(e);
    }
  },

  nextPending: () => {
    const currentId = get().activePending?.id;
    const queue = get().pendingQueue.filter((p) => p.id !== currentId);
    const next = queue[0] || null;
    set({
      pendingQueue: queue,
      activePending: next,
      modalOpen: !!next,
    });
  },

  downloadActive: async () => {
    const active = get().activePending;
    if (!active) return;

    set({ isDownloading: true });
    try {
      await downloadPendingLink(active.id);
      const toast = { id: generateId(), message: 'Added to queue', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      get().nextPending();
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to download', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isDownloading: false });
    }
  },

  dismissActive: async () => {
    const active = get().activePending;
    if (!active) return;

    try {
      await dismissPendingLink(active.id);
      get().nextPending();
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to dismiss', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    }
  },

  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));

