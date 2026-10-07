const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface CloudStatus {
  google_connected: boolean;
  dropbox_connected: boolean;
  cloud_backup_enabled: boolean;
  cloud_provider: string | null;
}

export interface AuthUrlResponse {
  url: string;
}

export interface BackupResponse {
  id: string;
  cloud_backed_up: boolean;
  cloud_url: string | null;
  message: string;
}

export async function getCloudStatus(): Promise<CloudStatus> {
  const res = await fetch(`${API_BASE}/cloud/status`);
  if (!res.ok) throw new Error('Failed to fetch cloud status');
  return res.json();
}

export async function getGoogleAuthUrl(): Promise<AuthUrlResponse> {
  const res = await fetch(`${API_BASE}/cloud/google/auth-url`);
  if (!res.ok) throw new Error('Failed to get Google auth URL');
  return res.json();
}

export async function connectDropbox(accessToken: string): Promise<CloudStatus> {
  const res = await fetch(`${API_BASE}/cloud/dropbox/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token: accessToken }),
  });
  if (!res.ok) throw new Error('Failed to connect Dropbox');
  return res.json();
}

export async function disconnectCloud(provider: string): Promise<CloudStatus> {
  const res = await fetch(`${API_BASE}/cloud/disconnect/${provider}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to disconnect cloud provider');
  return res.json();
}

export async function backupDownload(id: string): Promise<BackupResponse> {
  const res = await fetch(`${API_BASE}/downloads/${id}/backup`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to backup download');
  return res.json();
}
