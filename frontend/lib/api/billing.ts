export interface Plan {
  members: number;
  downloads_per_month: number;
  storage_gb: number;
  concurrent: number;
  days: number;
}

export interface PlansResponse {
  plans: Record<string, Plan>;
}

export interface CheckoutRequest {
  tenant_id: string;
  plan: string;
}

export interface CheckoutResponse {
  session_id: string;
  url: string;
}

export interface BillingTenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  owner_user_id: string | null;
  settings_json: Record<string, any> | null;
  created_at: string | null;
  suspended_at: string | null;
  plan_started_at: string | null;
  plan_expires_at: string | null;
  auto_renew: boolean;
  trial_used: boolean;
  quota_override_until: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function authHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function getPlans(token?: string): Promise<PlansResponse> {
  const res = await fetch(`${API_BASE}/billing/plans`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to fetch plans');
  return res.json();
}

export async function createCheckout(token: string, payload: CheckoutRequest): Promise<CheckoutResponse> {
  const res = await fetch(`${API_BASE}/billing/checkout`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Checkout failed' }));
    throw new Error(data.detail || 'Checkout failed');
  }
  return res.json();
}

export async function listTenants(token: string): Promise<BillingTenant[]> {
  const res = await fetch(`${API_BASE}/tenants`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to fetch tenants');
  return res.json();
}

export async function changeTenantPlan(token: string, tenantId: string, plan: string): Promise<BillingTenant> {
  const res = await fetch(`${API_BASE}/tenants/${tenantId}/plan`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ plan }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Failed to change plan' }));
    throw new Error(data.detail || 'Failed to change plan');
  }
  return res.json();
}

export async function setTenantExpiry(
  token: string,
  tenantId: string,
  plan_expires_at: string | null,
  auto_renew: boolean,
): Promise<BillingTenant> {
  const res = await fetch(`${API_BASE}/tenants/${tenantId}/expiry`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ plan_expires_at, auto_renew }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Failed to set expiry' }));
    throw new Error(data.detail || 'Failed to set expiry');
  }
  return res.json();
}

export async function waiveTenantQuota(
  token: string,
  tenantId: string,
  hours: number = 24,
): Promise<BillingTenant> {
  const res = await fetch(`${API_BASE}/tenants/${tenantId}/waive-quota`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ hours }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Failed to waive quota' }));
    throw new Error(data.detail || 'Failed to waive quota');
  }
  return res.json();
}

export async function cancelTenantSubscription(token: string, tenantId: string): Promise<{ cancelled: boolean }> {
  const res = await fetch(`${API_BASE}/billing/${tenantId}/cancel`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Failed to cancel' }));
    throw new Error(data.detail || 'Failed to cancel');
  }
  return res.json();
}
