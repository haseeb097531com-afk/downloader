export interface QueueEntry {
  id: string;
  title: string;
  platform: string;
  thumbnail_url: string | null;
  thumbnail_local: string | null;
  status: string;
  progress: number;
  speed: number | null;
  eta: number | null;
  downloaded_bytes: number | null;
  position: number | null;
  priority: number;
  created_at: string;
  error_message: string | null;
  processing_error: string | null;
  processed: boolean;
}

export interface QueueSnapshot {
  active: QueueEntry[];
  queued: QueueEntry[];
  paused: QueueEntry[];
  completed: QueueEntry[];
  active_count: number;
  queued_count: number;
  paused_count: number;
  completed_count: number;
  progress_source: string;
}

export interface QueueActionResult {
  affected: number;
  message: string;
}

export interface DownloadActionResult {
  id: string;
  status: string;
  celery_task_id: string | null;
  message: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getQueue(): Promise<QueueSnapshot> {
  const res = await fetch(`${API_BASE}/queue`);
  if (!res.ok) throw new Error('Failed to fetch queue');
  return res.json();
}

export async function prioritizeDownload(id: string): Promise<QueueEntry> {
  const res = await fetch(`${API_BASE}/queue/${id}/prioritize`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to prioritize download');
  return res.json();
}

export async function pauseAllDownloads(): Promise<QueueActionResult> {
  const res = await fetch(`${API_BASE}/queue/pause-all`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to pause all downloads');
  return res.json();
}

export async function resumeAllDownloads(): Promise<QueueActionResult> {
  const res = await fetch(`${API_BASE}/queue/resume-all`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resume all downloads');
  return res.json();
}

export async function pauseDownload(id: string): Promise<DownloadActionResult> {
  const res = await fetch(`${API_BASE}/downloads/${id}/pause`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to pause download');
  return res.json();
}

export async function resumeDownload(id: string): Promise<DownloadActionResult> {
  const res = await fetch(`${API_BASE}/downloads/${id}/resume`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resume download');
  return res.json();
}

export async function cancelDownload(id: string): Promise<DownloadActionResult> {
  const res = await fetch(`${API_BASE}/downloads/${id}/cancel`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to cancel download');
  return res.json();
}

export async function retryDownload(id: string): Promise<DownloadActionResult> {
  const res = await fetch(`${API_BASE}/downloads/${id}/retry`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to retry download');
  return res.json();
}
