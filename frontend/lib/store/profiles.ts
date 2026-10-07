import { create } from 'zustand';
import { Profile, ProfileVideo, listProfiles, getProfile, scrapeProfile, enqueueProfileDownloads, deleteProfile } from '../api/profiles';

interface ProfileState {
  profiles: Profile[];
  activeProfile: Profile | null;
  videos: ProfileVideo[];
  pagination: { page: number; total: number; limit: number };
  isScraping: boolean;
  scrapeProgress: { discovered: number; new_count: number; status: string } | null;
  selectedVideoIds: Set<string>;
  qualityPreference: string;

  fetchProfiles: () => Promise<void>;
  fetchProfileDetail: (id: string, page?: number) => Promise<void>;
  startScrape: (url: string, limit: number) => Promise<string>;
  subscribeScrapeProgress: (profileId: string) => void;
  enqueueDownloads: (profileId: string, videoIds?: string[], quality?: string) => Promise<void>;
  removeProfile: (id: string) => Promise<void>;
  toggleVideoSelection: (id: string) => void;
  clearSelection: () => void;
  setQuality: (quality: string) => void;
}

export const useProfileStore = create<ProfileState>((set, get) => ({
  profiles: [],
  activeProfile: null,
  videos: [],
  pagination: { page: 1, total: 0, limit: 50 },
  isScraping: false,
  scrapeProgress: null,
  selectedVideoIds: new Set(),
  qualityPreference: 'best',

  fetchProfiles: async () => {
    try {
      const profiles = await listProfiles();
      set({ profiles });
    } catch (e) {
      console.error(e);
    }
  },
  
  fetchProfileDetail: async (id, page = 1) => {
    try {
      const data = await getProfile(id, page);
      set({ activeProfile: data.profile, videos: data.videos });
    } catch (e) {
      console.error(e);
    }
  },

  startScrape: async (url, limit) => {
    set({ isScraping: true, scrapeProgress: { discovered: 0, new_count: 0, status: 'starting' } });
    try {
      const res = await scrapeProfile(url, limit);
      return res.task_id;
    } catch (e) {
      set({ isScraping: false, scrapeProgress: null });
      throw e;
    }
  },

  subscribeScrapeProgress: (profileId) => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
    const ws = new WebSocket(`${wsUrl}/scrape/${profileId}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      set({ scrapeProgress: data });
      if (data.status === 'completed' || data.status === 'failed') {
        set({ isScraping: false });
        ws.close();
      }
    };
  },

  enqueueDownloads: async (profileId, videoIds, quality) => {
    try {
      const currentQuality = quality || get().qualityPreference;
      await enqueueProfileDownloads(profileId, { video_ids: videoIds, quality: currentQuality });
      get().clearSelection();
      await get().fetchProfileDetail(profileId);
    } catch (e) {
      console.error(e);
      throw e;
    }
  },

  removeProfile: async (id) => {
    try {
      await deleteProfile(id);
      set((state) => ({ profiles: state.profiles.filter((p) => p.id !== id) }));
    } catch (e) {
      console.error(e);
      throw e;
    }
  },

  toggleVideoSelection: (id) => {
    const selected = new Set(get().selectedVideoIds);
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    set({ selectedVideoIds: selected });
  },

  clearSelection: () => set({ selectedVideoIds: new Set() }),
  setQuality: (quality) => set({ qualityPreference: quality }),
}));
