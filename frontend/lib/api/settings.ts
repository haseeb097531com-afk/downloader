export interface ProcessingSettings {
  auto_merge: boolean;
  embed_metadata: boolean;
  generate_thumbnails: boolean;
  max_cpu_percent: number;
  max_ram_percent: number;
  scraper_api_key: string;
  scraper_provider: string;
  rapid_api_key: string;
  provider_monthly_limit: number;
  fallback_enabled: boolean;
  auto_categorize: boolean;
  min_confidence: number;
  storage_guard_enabled: boolean;
  min_free_gb: number;
  ai_analysis_enabled: boolean;
  whisper_model: string;
  ollama_model: string;
  auto_translate_langs: string[];
  dedup_enabled: boolean;
  dedup_threshold: number;
  max_bandwidth_mbps: number;
  auto_adjust_quality: boolean;
  off_peak_enabled: boolean;
  off_peak_start: string;
  off_peak_end: string;
  turbo_mode: boolean;
  concurrent_fragments: number;
  push_enabled: boolean;
}

export interface KeyRegistryItem {
  name: string;
  label: string;
  category: string;
  required_for: string[];
  test: string;
  optional: boolean;
  secret: boolean;
  description?: string;
  note?: string;
}

export interface KeyRegistryResponse {
  keys: KeyRegistryItem[];
  categories: string[];
}

export interface KeyData {
  name: string;
  value: string;
  category: string;
  metadata: Record<string, unknown>;
  is_set: boolean;
  created_at: string;
  updated_at: string;
  last_test_status: string;
  last_test_at: string | null;
}

export interface KeyListResponse {
  keys: Record<string, KeyData>;
}

export interface KeyTestRequest {
  extra?: Record<string, unknown>;
}

export interface KeyTestResponse {
  name: string;
  status: string;
  message: string;
  tested_at: string;
}

export interface KeyCiphertextResponse {
  name: string;
  ciphertext_prefix: string;
}

export interface KeyCreateRequest {
  name: string;
  value: string;
  category: string;
  metadata?: Record<string, unknown>;
}

export interface KeyUpdateRequest {
  value?: string;
  category?: string;
  metadata?: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function getSettings(): Promise<ProcessingSettings> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function updateSettings(payload: Partial<ProcessingSettings>): Promise<ProcessingSettings> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update settings');
  return res.json();
}

// Key management API
export async function getKeyRegistry(): Promise<KeyRegistryResponse> {
  const res = await fetch(`${API_BASE}/settings/keys/registry`);
  if (!res.ok) throw new Error('Failed to fetch key registry');
  return res.json();
}

export async function listKeys(): Promise<Record<string, KeyData>> {
  const res = await fetch(`${API_BASE}/settings/keys`);
  if (!res.ok) throw new Error('Failed to fetch keys');
  const data = await res.json();
  return data.keys;
}

export async function createKey(payload: { name: string; value: string; category: string; metadata?: Record<string, unknown> }): Promise<{ name: string; value: string; category: string; is_set: boolean }> {
  const res = await fetch(`${API_BASE}/settings/keys/${payload.name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: payload.name, value: payload.value, category: payload.category, metadata: payload.metadata }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create key');
  }
  return res.json();
}

export async function updateKey(name: string, payload: { value?: string; category?: string; metadata?: Record<string, unknown> }): Promise<{ name: string; value: string; category: string; is_set: boolean }> {
  const res = await fetch(`${API_BASE}/settings/keys/${name}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update key');
  }
  return res.json();
}

export async function deleteKey(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/settings/keys/${name}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete key');
  }
}

export async function testKey(name: string): Promise<{ name: string; status: string; message: string; tested_at: string }> {
  const res = await fetch(`${API_BASE}/settings/keys/${name}/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to test key');
  }
  return res.json();
}

export async function getKeyCiphertext(name: string): Promise<{ name: string; ciphertext_prefix: string }> {
  const res = await fetch(`${API_BASE}/settings/keys/${name}/ciphertext`);
  if (!res.ok) throw new Error('Failed to fetch ciphertext');
  return res.json();
}

export async function getKeyRegistry(): Promise<{ keys: any[]; categories: string[] }> {
  const res = await fetch(`${API_BASE}/settings/keys/registry`);
  if (!res.ok) throw new Error('Failed to fetch key registry');
  return res.json();
}

