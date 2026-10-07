import { create } from 'zustand';
import { Schedule, listSchedules, createSchedule, updateSchedule, deleteSchedule } from '@/lib/api/schedules';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ScheduleState {
  schedules: Schedule[];
  isLoading: boolean;
  isSaving: boolean;
  toasts: Toast[];

  fetchSchedules: () => Promise<void>;
  createSchedule: (payload: { profile_id: string; frequency: 'daily' | 'weekly' | 'cron'; time_of_day: string; quality: string; is_active: boolean; days_of_week?: string[]; cron_expression?: string }) => Promise<void>;
  updateSchedule: (id: string, payload: Partial<{ frequency: 'daily' | 'weekly' | 'cron'; time_of_day: string; quality: string; is_active: boolean; days_of_week: string[] | null; cron_expression: string | null }>) => Promise<void>;
  removeSchedule: (id: string) => Promise<void>;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useScheduleStore = create<ScheduleState>((set, get) => ({
  schedules: [],
  isLoading: false,
  isSaving: false,
  toasts: [],

  fetchSchedules: async () => {
    set({ isLoading: true });
    try {
      const schedules = await listSchedules();
      set({ schedules });
    } catch (e) {
      console.error(e);
      get().addToast('Failed to load schedules', 'error');
    } finally {
      set({ isLoading: false });
    }
  },

  createSchedule: async (payload) => {
    set({ isSaving: true });
    try {
      const schedule = await createSchedule(payload);
      set((state) => ({ schedules: [...state.schedules, schedule] }));
      get().addToast('Schedule created successfully', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to create schedule', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  updateSchedule: async (id, payload) => {
    set({ isSaving: true });
    try {
      const schedule = await updateSchedule(id, payload);
      set((state) => ({
        schedules: state.schedules.map((s) => (s.id === id ? schedule : s)),
      }));
      get().addToast('Schedule updated successfully', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to update schedule', 'error');
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  removeSchedule: async (id) => {
    try {
      await deleteSchedule(id);
      set((state) => ({ schedules: state.schedules.filter((s) => s.id !== id) }));
      get().addToast('Schedule deleted', 'success');
    } catch (e) {
      console.error(e);
      get().addToast('Failed to delete schedule', 'error');
      throw e;
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
