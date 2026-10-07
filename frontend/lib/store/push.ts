import { create } from 'zustand';
import { getPublicKey, subscribePush, unsubscribePush, sendTestPush } from '../push/pushClient';
import { useSettingsStore } from '@/lib/store/settings';

interface PushState {
  permission: NotificationPermission | 'unsupported';
  isSupported: boolean;
  isSubscribed: boolean;
  isLoading: boolean;
  updateAvailable: boolean;
  swRegistration: ServiceWorkerRegistration | null;

  ensurePermission: () => Promise<NotificationPermission | 'unsupported'>;
  subscribe: () => Promise<void>;
  unsubscribe: () => Promise<void>;
  sendTest: () => Promise<void>;
  registerSW: () => Promise<void>;
  installUpdate: () => Promise<void>;
}

export const usePushStore = create<PushState>((set, get) => ({
  permission: 'default',
  isSupported: typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window,
  isSubscribed: false,
  isLoading: false,
  updateAvailable: false,
  swRegistration: null,

  ensurePermission: async () => {
    if (!('Notification' in window)) return 'unsupported';
    let perm = Notification.permission;
    if (perm === 'default') {
      perm = await Notification.requestPermission();
    }
    set({ permission: perm });
    return perm;
  },

  subscribe: async () => {
    const { isSupported, ensurePermission } = get();
    if (!isSupported) return;
    set({ isLoading: true });
    try {
      const perm = await ensurePermission();
      if (perm !== 'granted') return;

      const settings = useSettingsStore.getState().settings;
      const pushEnabled = settings.push_enabled !== false;
      if (!pushEnabled) return;

      const reg = await navigator.serviceWorker.ready;
      set({ swRegistration: reg });

      const { public_key } = await getPublicKey();
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: public_key,
      });

      await subscribePush(subscription);
      set({ isSubscribed: true });
    } catch (e) {
      console.error('Push subscribe failed:', e);
    } finally {
      set({ isLoading: false });
    }
  },

  unsubscribe: async () => {
    const { swRegistration } = get();
    if (!swRegistration) return;
    set({ isLoading: true });
    try {
      const subscription = await swRegistration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();
        await unsubscribePush();
      }
      set({ isSubscribed: false });
    } catch (e) {
      console.error('Push unsubscribe failed:', e);
    } finally {
      set({ isLoading: false });
    }
  },

  sendTest: async () => {
    set({ isLoading: true });
    try {
      await sendTestPush();
      useSettingsStore.getState().addToast('Test notification sent', 'success');
    } catch (e) {
      console.error('Test push failed:', e);
      useSettingsStore.getState().addToast('Failed to send test notification', 'error');
    } finally {
      set({ isLoading: false });
    }
  },

  registerSW: async () => {
    if (!get().isSupported) return;
    try {
      const reg = await navigator.serviceWorker.register('/sw.js');
      set({ swRegistration: reg });

      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (!newWorker) return;
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            set({ updateAvailable: true });
          }
        });
      });

      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'PUSH_NOTIFICATION') {
          const { title, body } = event.data.payload;
          if (document.visibilityState === 'visible') {
            useSettingsStore.getState().addToast(`${title}: ${body}`, 'info');
          }
        }
      });
    } catch (e) {
      console.error('SW registration failed:', e);
    }
  },

  installUpdate: async () => {
    const { swRegistration } = get();
    if (!swRegistration || !swRegistration.waiting) return;
    swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
    set({ updateAvailable: false });
    useSettingsStore.getState().addToast('Update installed. Reloading...', 'success');
    setTimeout(() => window.location.reload(), 1000);
  },
}));

