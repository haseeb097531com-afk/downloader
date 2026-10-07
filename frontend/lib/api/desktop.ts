export interface DesktopStatus {
  clipboard_running: boolean;
  tray_running: boolean;
  clipboard_enabled: boolean;
  tray_enabled: boolean;
}

export interface PendingLink {
  id: string;
  url: string;
  platform: string;
  detected_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function getDesktopStatus(): Promise<DesktopStatus> {
  const res = await fetch(`${API_BASE}/desktop/status`);
  if (!res.ok) throw new Error('Failed to fetch desktop status');
  return res.json();
}

export async function startDesktopServices(
  options: { clipboard?: boolean; tray?: boolean } = {}
): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/desktop/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) throw new Error('Failed to start desktop services');
  return res.json();
}

export async function stopDesktopServices(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/desktop/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop desktop services');
  return res.json();
}

export async function getPendingLinks(): Promise<PendingLink[]> {
  const res = await fetch(`${API_BASE}/desktop/pending`);
  if (!res.ok) throw new Error('Failed to fetch pending links');
  return res.json();
}

export async function dismissPendingLink(id: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/desktop/pending/${id}/dismiss`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to dismiss pending link');
  return res.json();
}

export async function downloadPendingLink(id: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/desktop/pending/${id}/download`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to download pending link');
  return res.json();
}

