import { create } from 'zustand';
import { PluginInfo } from '@/lib/api/plugins';
import { getPlugins, installPlugin, uninstallPlugin, reloadPlugins } from '@/lib/api/plugins';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface PluginsState {
  core: PluginInfo[];
  user: PluginInfo[];
  isLoading: boolean;
  isInstalling: boolean;
  isReloading: boolean;
  toasts: Toast[];

  fetchPlugins: () => Promise<void>;
  installPlugin: (repoUrl: string) => Promise<void>;
  uninstallPlugin: (name: string) => Promise<void>;
  reloadPlugins: () => Promise<void>;
  togglePlugin: (name: string) => Promise<void>;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const usePluginsStore = create<PluginsState>((set, get) => ({
  core: [],
  user: [],
  isLoading: false,
  isInstalling: false,
  isReloading: false,
  toasts: [],

  fetchPlugins: async () => {
    set({ isLoading: true });
    try {
      const data = await getPlugins();
      set({ core: data.core, user: data.user });
    } catch (e) {
      console.error(e);
      get().addToast('Failed to load plugins', 'error');
    } finally {
      set({ isLoading: false });
    }
  },

  installPlugin: async (repoUrl: string) => {
    set({ isInstalling: true });
    try {
      await installPlugin(repoUrl);
      get().addToast('Plugin installed successfully', 'success');
      await get().fetchPlugins();
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to install plugin';
      get().addToast(message, 'error');
      throw e;
    } finally {
      set({ isInstalling: false });
    }
  },

  uninstallPlugin: async (name: string) => {
    try {
      await uninstallPlugin(name);
      set((state) => ({
        user: state.user.filter((p) => p.name !== name),
      }));
      get().addToast('Plugin uninstalled', 'success');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to uninstall plugin';
      get().addToast(message, 'error');
      throw e;
    }
  },

  reloadPlugins: async () => {
    set({ isReloading: true });
    try {
      await reloadPlugins();
      get().addToast('Plugins reloaded successfully', 'success');
      await get().fetchPlugins();
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to reload plugins';
      get().addToast(message, 'error');
    } finally {
      set({ isReloading: false });
    }
  },

  togglePlugin: async (name: string) => {
    const plugin = get().user.find((p) => p.name === name);
    if (!plugin) return;

    const newStatus = plugin.status === 'active' ? 'disabled' : 'active';
    set((state) => ({
      user: state.user.map((p) => (p.name === name ? { ...p, status: newStatus } : p)),
    }));

    try {
      get().addToast(`Plugin ${newStatus === 'active' ? 'enabled' : 'disabled'}`, 'success');
    } catch (e) {
      set((state) => ({
        user: state.user.map((p) => (p.name === name ? { ...p, status: plugin.status } : p)),
      }));
      const message = e instanceof Error ? e.message : 'Failed to toggle plugin';
      get().addToast(message, 'error');
    }
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

