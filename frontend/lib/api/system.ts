export interface SystemStats {
  cpu_percent: number;
  ram_percent: number;
  is_throttled: boolean;
}

export interface DiskStatus {
  total_gb: number;
  free_gb: number;
  used_percent: number;
  guard_active: boolean;
}

export interface NetworkStatus {
  speed_mbps: number;
  latency_ms: number;
  is_online: boolean;
  recommended_quality: string;
}

export interface SystemSpeed {
  turbo_mode: boolean;
  aria2_available: boolean;
  concurrent_fragments: number;
  active_workers: number;
  current_speed_mbps: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getSystemStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/system/stats`);
  if (!res.ok) throw new Error('Failed to fetch system stats');
  return res.json();
}

export async function getDiskStatus(): Promise<DiskStatus> {
  const res = await fetch(`${API_BASE}/system/disk`);
  if (!res.ok) throw new Error('Failed to fetch disk status');
  return res.json();
}

export async function getNetworkStatus(): Promise<NetworkStatus> {
  const res = await fetch(`${API_BASE}/system/network`);
  if (!res.ok) throw new Error('Failed to fetch network status');
  return res.json();
}

export async function getSystemSpeed(): Promise<SystemSpeed> {
  const res = await fetch(`${API_BASE}/system/speed`);
  if (!res.ok) throw new Error('Failed to fetch system speed');
  return res.json();
}
