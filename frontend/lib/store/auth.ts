import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  login,
  refreshToken,
  logout as apiLogout,
  getMe,
  User,
} from '@/lib/api/auth';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  authEnabled: boolean;
  isBootstrapping: boolean;
  toasts: Toast[];

  bootstrap: () => Promise<void>;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
  updateUser: (user: User) => void;
  setAuthEnabled: (enabled: boolean) => void;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      authEnabled: true,
      isBootstrapping: true,
      toasts: [],

      bootstrap: async () => {
        const { accessToken, refreshToken: storedRefresh } = get();
        if (!accessToken) {
          set({ isBootstrapping: false });
          return;
        }
        try {
          const user = await getMe(accessToken);
          set({ user, isAuthenticated: true, isBootstrapping: false });
        } catch {
          if (storedRefresh) {
            try {
              const refreshed = await refreshToken(storedRefresh);
              const user = await getMe(refreshed.access_token);
              set({
                user,
                accessToken: refreshed.access_token,
                refreshToken: refreshed.refresh_token,
                isAuthenticated: true,
                isBootstrapping: false,
              });
              return;
            } catch {
              // fall through to clear
            }
          }
          set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false, isBootstrapping: false });
        }
      },

      login: async (usernameOrEmail, password) => {
        const response = await login({ username_or_email: usernameOrEmail, password });
        set({
          user: response.user,
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          isAuthenticated: true,
        });
      },

      logout: async () => {
        try {
          await apiLogout();
        } catch {
          // best-effort
        }
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },

      refreshSession: async () => {
        const { refreshToken: storedRefresh } = get();
        if (!storedRefresh) return false;
        try {
          const refreshed = await refreshToken(storedRefresh);
          const user = await getMe(refreshed.access_token);
          set({
            user,
            accessToken: refreshed.access_token,
            refreshToken: refreshed.refresh_token,
            isAuthenticated: true,
          });
          return true;
        } catch {
          set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
          return false;
        }
      },

      updateUser: (user) => set({ user }),

      setAuthEnabled: (authEnabled) => set({ authEnabled }),

      addToast: (message, type) => {
        const toast = { id: generateId(), message, type };
        set((state) => ({ toasts: [...state.toasts, toast] }));
        setTimeout(() => get().dismissToast(toast.id), 4000);
      },

      dismissToast: (id) => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
);

