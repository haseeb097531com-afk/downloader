import { create } from 'zustand';
import { ModerationSettings, QuarantinedItem, getModerationSettings, updateModerationSettings, setPin, verifyPin, getQuarantined, restoreItem, purgeItem } from '@/lib/api/moderation';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ModerationState {
  settings: ModerationSettings | null;
  quarantined: QuarantinedItem[];
  isLoading: boolean;
  isSaving: boolean;
  isUnlocked: boolean;
  toasts: Toast[];

  fetchSettings: () => Promise<void>;
  updateSettings: (payload: Partial<ModerationSettings>) => Promise<void>;
  setPin: (pin: string) => Promise<void>;
  verifyPin: (pin: string) => Promise<boolean>;
  fetchQuarantined: () => Promise<void>;
  restoreItem: (id: string) => Promise<void>;
  purgeItem: (id: string) => Promise<void>;
  unlock: () => void;
  lock: () => void;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useModerationStore = create<ModerationState>((set, get) => ({
  settings: null,
  quarantined: [],
  isLoading: false,
  isSaving: false,
  isUnlocked: false,
  toasts: [],

  fetchSettings: async () => {
    set({ isLoading: true });
    try {
      const settings = await getModerationSettings();
      set({ settings });
    } catch (e) {
      console.error(e);
      get().addToast('Failed to load safety settings', 'error');
    } finally {
      set({ isLoading: false });
    }
  },

  updateSettings: async (payload) => {
    set({ isSaving: true });
    try {
      const settings = await updateModerationSettings(payload);
      set({ settings });
      get().addToast('Safety settings updated', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to update settings', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  setPin: async (pin) => {
    set({ isSaving: true });
    try {
      await setPin(pin);
      set((state) => ({
        settings: state.settings ? { ...state.settings, pin_set: true } : null,
      }));
      get().addToast('PIN set successfully', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to set PIN', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  verifyPin: async (pin) => {
    try {
      const result = await verifyPin(pin);
      if (result.success) {
        set({ isUnlocked: true });
        get().addToast('PIN verified', 'success');
        return true;
      }
      get().addToast('Incorrect PIN', 'error');
      return false;
    } catch (e) {
      console.error(e);
      get().addToast('Failed to verify PIN', 'error');
      return false;
    }
  },

  fetchQuarantined: async () => {
    set({ isLoading: true });
    try {
      const items = await getQuarantined();
      set({ quarantined: items });
    } catch (e) {
      console.error(e);
      get().addToast('Failed to load quarantined items', 'error');
    } finally {
      set({ isLoading: false });
    }
  },

  restoreItem: async (id) => {
    set({ isSaving: true });
    try {
      await restoreItem(id);
      set((state) => ({
        quarantined: state.quarantined.filter((item) => item.id !== id),
      }));
      get().addToast('Item restored successfully', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to restore item', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  purgeItem: async (id) => {
    set({ isSaving: true });
    try {
      await purgeItem(id);
      set((state) => ({
        quarantined: state.quarantined.filter((item) => item.id !== id),
      }));
      get().addToast('Item deleted forever', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to delete item', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  unlock: () => set({ isUnlocked: true }),
  lock: () => set({ isUnlocked: false }),

  addToast: (message, type) => {
    const toast = { id: generateId(), message, type };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    setTimeout(() => get().dismissToast(toast.id), 4000);
  },

  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));
