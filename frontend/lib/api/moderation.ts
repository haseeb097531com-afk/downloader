export interface ModerationSettings {
  safe_mode_enabled: boolean;
  sensitivity: number;
  blacklist: string[];
  pin_set: boolean;
}

export interface QuarantinedItem {
  id: string;
  title: string;
  thumbnail: string | null;
  reason: string;
  created_at: string;
}

export interface PinResponse {
  success: boolean;
  message?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function getModerationSettings(): Promise<ModerationSettings> {
  const res = await fetch(`${API_BASE}/moderation/settings`);
  if (!res.ok) throw new Error('Failed to fetch moderation settings');
  return res.json();
}

export async function updateModerationSettings(payload: Partial<ModerationSettings>): Promise<ModerationSettings> {
  const res = await fetch(`${API_BASE}/moderation/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update moderation settings');
  return res.json();
}

export async function setPin(pin: string): Promise<PinResponse> {
  const res = await fetch(`${API_BASE}/moderation/set-pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pin }),
  });
  if (!res.ok) throw new Error('Failed to set PIN');
  return res.json();
}

export async function verifyPin(pin: string): Promise<PinResponse> {
  const res = await fetch(`${API_BASE}/moderation/verify-pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pin }),
  });
  if (!res.ok) throw new Error('Failed to verify PIN');
  return res.json();
}

export async function getQuarantined(): Promise<QuarantinedItem[]> {
  const res = await fetch(`${API_BASE}/moderation/quarantined`);
  if (!res.ok) throw new Error('Failed to fetch quarantined items');
  return res.json();
}

export async function restoreItem(id: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/moderation/restore/${id}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to restore item');
  return res.json();
}

export async function purgeItem(id: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/moderation/purge/${id}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to purge item');
  return res.json();
}

