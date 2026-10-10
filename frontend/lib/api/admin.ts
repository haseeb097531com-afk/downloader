import { BillingTenant } from './billing';
import { User } from './auth';

export interface AdminStats {
  total_tenants: number;
  active_tenants: number;
  pending_payments: number;
  total_members: number;
  downloads_today: number;
  downloads_this_month: number;
  approved_revenue_this_month: number;
  backend_ok: boolean;
  redis_ok: boolean;
  celery_ok: boolean;
  disk_free_gb: number;
  downloads_last_7_days: Array<{ date: string; count: number }>;
}

export interface AdminHealth {
  backend_ok: boolean;
  redis_ok: boolean;
  celery_ok: boolean;
  disk_free_gb: number;
}

export interface AdminUser {
  id: string;
  username: string;
  email: string | null;
  role: string;
  tenant_id: string | null;
  tenant_name: string | null;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export interface AdminTenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  owner_user_id: string | null;
  created_at: string | null;
  member_count: number;
}

export interface AdminPayment {
  id: string;
  tenant_id: string;
  tenant_name: string;
  plan: string;
  amount: number;
  reference: string;
  status: string;
  created_at: string;
  screenshot_url: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

function authHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getAdminStats(token: string): Promise<AdminStats> {
  const res = await fetch(`${API_BASE}/admin/stats`, { headers: authHeaders(token) });
  return handleResponse<AdminStats>(res);
}

export async function getAdminHealth(token: string): Promise<AdminHealth> {
  const res = await fetch(`${API_BASE}/admin/health`, { headers: authHeaders(token) });
  return handleResponse<AdminHealth>(res);
}

export async function listAdminUsers(
  token: string,
  params?: { tenant_id?: string; search?: string; limit?: number; offset?: number }
): Promise<any[]> {
  const searchParams = new URLSearchParams();
  if (params?.tenant_id) searchParams.set('tenant_id', params.tenant_id);
  if (params?.search) searchParams.set('search', params.search);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const res = await fetch(`${API_BASE}/admin/users?${searchParams}`, { headers: authHeaders(token) });
  return handleResponse<any[]>(res);
}

export async function listAdminTenants(token: string): Promise<any[]> {
  const res = await fetch(`${API_BASE}/admin/tenants`, { headers: authHeaders(token) });
  return handleResponse<any[]>(res);
}

export interface AdminPayment {
  id: string;
  tenant_id: string;
  tenant_name: string;
  plan: string;
  amount: number;
  reference: string;
  status: string;
  created_at: string;
  screenshot_url: string | null;
}

export async function listAdminPayments(
  token: string,
  params?: { status?: string; limit?: number; offset?: number }
): Promise<any[]> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const res = await fetch(`${API_BASE}/admin/payments?${searchParams}`, { headers: authHeaders(token) });
  return handleResponse<any[]>(res);
}

export async function approveAdminPayment(token: string, paymentId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/payments/${paymentId}/approve`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return handleResponse<any>(res);
}

export async function rejectAdminPayment(token: string, paymentId: string, reason?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/payments/${paymentId}/reject`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  return handleResponse<any>(res);
}

export async function getSystemHealth(token: string): Promise<any> {
  const res = await fetch(`${API_BASE}/system/health`, { headers: authHeaders(token) });
  return handleResponse<any>(res);
}