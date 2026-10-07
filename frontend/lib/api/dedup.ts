export interface DuplicateMatch {
  download_id: string;
  title: string;
  thumbnail_url: string | null;
  similarity: number;
  platform: string;
}

export interface DedupCheckResponse {
  matches: DuplicateMatch[];
}

export interface DedupKeepItem {
  id: string;
  title: string;
  platform: string;
  thumbnail_url: string | null;
}

export interface DedupReportGroup {
  keep: DedupKeepItem;
  duplicates: Array<{
    id: string;
    title: string;
    similarity: number;
    platform: string;
    thumbnail_url: string | null;
  }>;
}

export interface DedupReportResponse {
  groups: DedupReportGroup[];
}

export interface DedupCleanupRequest {
  delete_ids: string[];
}

export interface DedupCleanupResponse {
  deleted_count: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function checkDedupUrl(url: string): Promise<DedupCheckResponse> {
  const res = await fetch(`${API_BASE}/dedup/check?${new URLSearchParams({ url })}`);
  if (!res.ok) throw new Error('Failed to check duplicates');
  return res.json();
}

export async function startDedupScan(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/library/dedup-scan`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start dedup scan');
  return res.json();
}

export async function getDedupReport(): Promise<DedupReportResponse> {
  const res = await fetch(`${API_BASE}/library/dedup-report`);
  if (!res.ok) throw new Error('Failed to fetch dedup report');
  return res.json();
}

export async function dedupCleanup(deleteIds: string[]): Promise<DedupCleanupResponse> {
  const res = await fetch(`${API_BASE}/library/dedup-cleanup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ delete_ids: deleteIds }),
  });
  if (!res.ok) throw new Error('Failed to cleanup duplicates');
  return res.json();
}
