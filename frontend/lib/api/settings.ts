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

