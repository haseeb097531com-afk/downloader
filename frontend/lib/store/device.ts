import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  createDeviceIntent,
  getDevices,
  updateDevicePermissions,
  renameDevice,
  revokeDevice,
  Device,
  DevicePairResponse,
} from '@/lib/api/remote';

export type { DevicePairResponse } from '@/lib/api/remote';

interface DeviceState {
  deviceId: string | null;
  token: string | null;
  name: string | null;
  permissions: string[];
  devices: Device[];
  isPairing: boolean;
  pairData: DevicePairResponse | null;
  error: string | null;

  pair: (code: string, name: string) => Promise<void>;
  startPair: (name: string, permissions: string[]) => Promise<void>;
  unpair: () => Promise<void>;
  refreshDevices: () => Promise<void>;
  updatePermissions: (id: string, permissions: string[]) => Promise<void>;
  rename: (id: string, name: string) => Promise<void>;
  revoke: (id: string) => Promise<void>;
  clearPairData: () => void;
  isPaired: () => boolean;
  hasPermission: (p: string) => boolean;
}

export const useDeviceStore = create<DeviceState>()(
  persist(
    (set, get) => ({
      deviceId: null,
      token: null,
      name: null,
      permissions: [],
      devices: [],
      isPairing: false,
      pairData: null,
      error: null,

      startPair: async (name, permissions) => {
        set({ isPairing: true, error: null });
        try {
          const data = await createDeviceIntent({ name, permissions });
          set({ pairData: data });
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Pairing failed';
          set({ error: message, isPairing: false });
        }
      },

      pair: async (code, name) => {
        set({ isPairing: true, error: null });
        try {
          const res = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL || '/api/v1'}/devices/pair`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ code, name }),
            }
          );
          if (!res.ok) throw new Error('Pairing failed');
          const data = await res.json();
          set({
            deviceId: data.device_id,
            token: data.token,
            name: data.name,
            permissions: data.permissions || [],
            isPairing: false,
            pairData: null,
          });
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Pairing failed';
          set({ error: message, isPairing: false });
        }
      },

      unpair: async () => {
        const { deviceId } = get();
        try {
          if (deviceId) {
            await revokeDevice(deviceId);
          }
        } catch {
          // best-effort
        }
        set({ deviceId: null, token: null, name: null, permissions: [], devices: [] });
      },

      refreshDevices: async () => {
        try {
          const devices = await getDevices();
          set({ devices });
        } catch (e) {
          console.error(e);
        }
      },

      updatePermissions: async (id, permissions) => {
        try {
          const updated = await updateDevicePermissions(id, permissions);
          set((state) => ({
            devices: state.devices.map((d) => (d.id === id ? updated : d)),
          }));
        } catch (e) {
          console.error(e);
        }
      },

      rename: async (id, name) => {
        try {
          const updated = await renameDevice(id, name);
          set((state) => ({
            devices: state.devices.map((d) => (d.id === id ? updated : d)),
          }));
        } catch (e) {
          console.error(e);
        }
      },

      revoke: async (id) => {
        try {
          await revokeDevice(id);
          set((state) => ({
            devices: state.devices.filter((d) => d.id !== id),
          }));
        } catch (e) {
          console.error(e);
        }
      },

      clearPairData: () => set({ pairData: null, error: null }),

      isPaired: () => !!get().token && !!get().deviceId,

      hasPermission: (p) => get().permissions.includes(p),
    }),
    {
      name: 'device-storage',
      partialize: (state) => ({
        deviceId: state.deviceId,
        token: state.token,
        name: state.name,
        permissions: state.permissions,
      }),
    }
  )
);

