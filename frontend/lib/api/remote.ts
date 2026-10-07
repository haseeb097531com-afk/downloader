export interface DeviceIntentPayload {
  name: string;
  permissions: string[];
}

export interface DevicePairResponse {
  code: string;
  qr_payload: string;
  expires_at: string;
}

export interface Device {
  id: string;
  name: string;
  platform: string;
  permissions: string[];
  last_seen: string;
  created_at: string;
}

export interface RemoteSummary {
  disk_free_gb: number;
  disk_total_gb: number;
  active_workers: number;
  current_speed_mbps: number;
  turbo_mode: boolean;
  queue_length: number;
}

export interface RemoteQueueItem {
  id: string;
  title: string;
  status: string;
  progress: number;
  platform: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function createDeviceIntent(payload: DeviceIntentPayload): Promise<DevicePairResponse> {
  const res = await fetch(`${API_BASE}/devices/intent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create pairing intent');
  return res.json();
}

export async function getDevices(): Promise<Device[]> {
  const res = await fetch(`${API_BASE}/devices`);
  if (!res.ok) throw new Error('Failed to fetch devices');
  return res.json();
}

export async function updateDevicePermissions(id: string, permissions: string[]): Promise<Device> {
  const res = await fetch(`${API_BASE}/devices/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ permissions }),
  });
  if (!res.ok) throw new Error('Failed to update device');
  return res.json();
}

export async function renameDevice(id: string, name: string): Promise<Device> {
  const res = await fetch(`${API_BASE}/devices/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error('Failed to rename device');
  return res.json();
}

export async function revokeDevice(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/devices/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to revoke device');
}

export async function getRemoteSummary(): Promise<RemoteSummary> {
  const res = await fetch(`${API_BASE}/remote/summary`);
  if (!res.ok) throw new Error('Failed to fetch summary');
  return res.json();
}

export async function getRemoteQueue(): Promise<RemoteQueueItem[]> {
  const res = await fetch(`${API_BASE}/remote/queue`);
  if (!res.ok) throw new Error('Failed to fetch queue');
  return res.json();
}

export async function pauseRemoteQueue(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/remote/queue/pause`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to pause queue');
  return res.json();
}

export async function resumeRemoteQueue(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/remote/queue/resume`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resume queue');
  return res.json();
}

export async function cancelRemoteItem(id: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/remote/queue/${id}/cancel`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to cancel item');
  return res.json();
}

export async function submitClipboardUrl(url: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/clipboard/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error('Failed to submit URL');
  return res.json();
}

export interface FormatOption {
  format_id: string;
  quality: string;
  extension: string;
  url: string;
  file_size_estimate: number | null;
  is_watermark_free: boolean;
  resolution: string | null;
  codec: string | null;
}

export interface FormatsResponse {
  url: string;
  formats: FormatOption[];
  max_height: number;
}

export async function getMediaFormats(url: string): Promise<FormatsResponse> {
  const res = await fetch(`${API_BASE}/media/formats?url=${encodeURIComponent(url)}`);
  if (!res.ok) throw new Error('Failed to fetch media formats');
  return res.json();
}

export async function createDownloadRemote(payload: { url: string; quality?: string; trim_start?: string; trim_end?: string }): Promise<{ message: string; id?: string }> {
  const res = await fetch(`${API_BASE}/downloads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to start download');
  return res.json();
}

export async function getRecentDownloads(limit = 10): Promise<RemoteQueueItem[]> {
  const res = await fetch(`${API_BASE}/remote/downloads?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch recent downloads');
  return res.json();
}

