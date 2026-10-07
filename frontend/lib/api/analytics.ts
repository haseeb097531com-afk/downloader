export interface AnalyticsOverview {
  total_downloads: number;
  total_size_bytes: number;
  active_profiles: number;
  avg_daily_downloads: number;
  top_platform: string | null;
  growth_percent: number;
}

export interface TimelineDataPoint {
  date: string;
  downloads: number;
  size_bytes: number;
}

export interface CreatorStat {
  username: string;
  count: number;
  total_size: number;
}

export interface StorageStat {
  used_bytes: number;
  total_bytes: number;
  free_bytes: number;
  percent_used: number;
}

export interface ExportResponse {
  url: string;
  filename: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const res = await fetch(`${API_BASE}/analytics/overview`);
  if (!res.ok) throw new Error('Failed to fetch analytics overview');
  return res.json();
}

export async function getAnalyticsTimeline(range = '7d'): Promise<TimelineDataPoint[]> {
  const res = await fetch(`${API_BASE}/analytics/timeline?range=${range}`);
  if (!res.ok) throw new Error('Failed to fetch analytics timeline');
  return res.json();
}

export async function getAnalyticsCreators(): Promise<CreatorStat[]> {
  const res = await fetch(`${API_BASE}/analytics/creators`);
  if (!res.ok) throw new Error('Failed to fetch analytics creators');
  return res.json();
}

export async function getAnalyticsStorage(): Promise<StorageStat> {
  const res = await fetch(`${API_BASE}/analytics/storage`);
  if (!res.ok) throw new Error('Failed to fetch analytics storage');
  return res.json();
}

export async function exportAnalyticsCsv(range = '7d'): Promise<ExportResponse> {
  const res = await fetch(`${API_BASE}/analytics/export/csv?range=${range}`);
  if (!res.ok) throw new Error('Failed to export analytics CSV');
  return res.json();
}

export async function exportAnalyticsPdf(range = '7d'): Promise<ExportResponse> {
  const res = await fetch(`${API_BASE}/analytics/export/pdf?range=${range}`);
  if (!res.ok) throw new Error('Failed to export analytics PDF');
  return res.json();
}
