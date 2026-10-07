export interface BulkJobItem {
  id: string;
  url: string;
  platform: string;
  status: 'queued' | 'downloading' | 'completed' | 'failed';
  error?: string;
}

export interface BulkJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total: number;
  completed: number;
  failed: number;
  items: BulkJobItem[];
}

export interface BulkLinksRequest {
  links: string[];
}

export interface BulkProfilesRequest {
  profiles: string[];
  limit_per_profile?: number;
}

export interface BulkJobResponse {
  job_id: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function bulkImportLinks(payload: BulkLinksRequest): Promise<BulkJobResponse> {
  const res = await fetch(`${API_BASE}/bulk/links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to start bulk links import');
  return res.json();
}

export async function bulkImportProfiles(payload: BulkProfilesRequest): Promise<BulkJobResponse> {
  const res = await fetch(`${API_BASE}/bulk/profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to start bulk profiles import');
  return res.json();
}

export async function getBulkJob(jobId: string): Promise<BulkJobStatus> {
  const res = await fetch(`${API_BASE}/bulk/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch bulk job');
  return res.json();
}

export async function retryBulkJob(jobId: string): Promise<{ retried: number }> {
  const res = await fetch(`${API_BASE}/bulk/${jobId}/retry`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to retry bulk job');
  return res.json();
}

