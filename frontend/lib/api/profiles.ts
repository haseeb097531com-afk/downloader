export interface ProfileStats {
  total_videos: number;
  downloaded_count: number;
  new_count: number;
}

export interface Profile {
  id: string;
  platform: string;
  username: string;
  profile_url: string;
  display_name: string | null;
  avatar_url: string | null;
  total_videos: number;
  last_scraped_at: string | null;
  auto_download: boolean;
}

export interface ProfileVideo {
  id: string;
  video_url: string;
  title: string | null;
  thumbnail_url: string | null;
  upload_date: string | null;
  status: 'new' | 'queued' | 'downloaded' | 'skipped' | 'failed';
  download_id: string | null;
}

export interface ProfileDetail {
  profile: Profile;
  videos: ProfileVideo[];
}

export interface ScrapeResponse {
  message: string;
  task_id: string;
}

export interface BulkEnqueueResponse {
  enqueued: number;
  skipped: number;
  failed: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function listProfiles(): Promise<Profile[]> {
  const res = await fetch(`${API_BASE}/profiles/`);
  if (!res.ok) throw new Error('Failed to fetch profiles');
  return res.json();
}

export async function getProfile(id: string, page: number = 1): Promise<ProfileDetail> {
  const res = await fetch(`${API_BASE}/profiles/${id}?page=${page}`);
  if (!res.ok) throw new Error('Failed to fetch profile details');
  return res.json();
}

export async function scrapeProfile(url: string, limit: number): Promise<ScrapeResponse> {
  const res = await fetch(`${API_BASE}/profiles/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, limit }),
  });
  if (!res.ok) throw new Error('Failed to start scrape');
  return res.json();
}

export async function enqueueProfileDownloads(id: string, payload: { video_ids?: string[]; quality: string }): Promise<BulkEnqueueResponse> {
  const res = await fetch(`${API_BASE}/profiles/${id}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to enqueue downloads');
  return res.json();
}

export async function deleteProfile(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/profiles/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete profile');
}
