import { create } from 'zustand';
import { getSettings, updateSettings, ProcessingSettings } from '@/lib/api/settings';
import { getProviderStatus, testProvider, ProviderStatusItem, ProviderStatusResponse } from '@/lib/api/providers';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface SettingsState {
  settings: ProcessingSettings;
  isLoading: boolean;
  isSaving: boolean;
  toasts: Toast[];
  providers: ProviderStatusItem[];
  attempts: ProviderStatusResponse['recent_attempts'];
  testingProvider: string | null;
  isProvidersLoading: boolean;

  fetchSettings: () => Promise<void>;
  saveSettings: (payload: Partial<ProcessingSettings>) => Promise<void>;
  fetchProviders: () => Promise<void>;
  runProviderTest: (provider: string) => Promise<void>;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: {
    auto_merge: true,
    embed_metadata: true,
    generate_thumbnails: true,
    max_cpu_percent: 90,
    max_ram_percent: 90,
    scraper_api_key: '',
    scraper_provider: 'scraperapi',
    rapid_api_key: '',
    provider_monthly_limit: 1000,
    fallback_enabled: true,
    auto_categorize: true,
    min_confidence: 0.7,
    storage_guard_enabled: true,
    min_free_gb: 10,
    ai_analysis_enabled: false,
    whisper_model: 'base',
    ollama_model: 'llama3',
    auto_translate_langs: [],
    dedup_enabled: true,
    dedup_threshold: 6,
    max_bandwidth_mbps: 0,
    auto_adjust_quality: false,
    off_peak_enabled: false,
    off_peak_start: '23:00',
    off_peak_end: '06:00',
    turbo_mode: false,
    concurrent_fragments: 8,
    push_enabled: false,
  },
  isLoading: false,
  isSaving: false,
  toasts: [],
  providers: [],
  attempts: [],
  testingProvider: null,
  isProvidersLoading: false,

  fetchSettings: async () => {
    set({ isLoading: true });
    try {
      const settings = await getSettings();
      set({ settings });
    } catch (e) {
      console.error(e);
      get().addToast('Failed to load settings', 'error');
    } finally {
      set({ isLoading: false });
    }
  },

  saveSettings: async (payload) => {
    set({ isSaving: true });
    try {
      const updated = await updateSettings(payload);
      set({ settings: updated });
      get().addToast('Settings saved successfully', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to save settings', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  fetchProviders: async () => {
    set({ isProvidersLoading: true });
    try {
      const data = await getProviderStatus();
      set({ providers: data.providers, attempts: data.recent_attempts });
    } catch {
      console.error();
    } finally {
      set({ isProvidersLoading: false });
    }
  },

  runProviderTest: async (provider) => {
    set({ testingProvider: provider });
    try {
      const result = await testProvider(provider);
      if (result.success) {
        get().addToast('Connection successful', 'success');
      } else {
        get().addToast(result.message || 'Connection failed', 'error');
      }
    } catch {
      get().addToast('Failed to test provider', 'error');
    } finally {
      set({ testingProvider: null });
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


