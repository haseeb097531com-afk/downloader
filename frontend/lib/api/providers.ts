export interface ProviderStatusItem {
  name: string;
  enabled: boolean;
  has_key: boolean;
  used_this_month: number;
  monthly_limit: number;
  remaining: number;
  status: string;
}

export interface ProviderStatusResponse {
  providers: ProviderStatusItem[];
  recent_attempts: {
    url: string;
    provider: string;
    success: boolean;
    error_message: string | null;
    latency_ms: number | null;
    created_at: string | null;
  }[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function getProviderStatus(): Promise<ProviderStatusResponse> {
  const res = await fetch(`${API_BASE}/providers/status`);
  if (!res.ok) throw new Error('Failed to fetch provider status');
  return res.json();
}

export async function testProvider(provider: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/providers/test/${provider}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to test provider');
  return res.json();
}

