export interface User {
  id: string;
  username: string;
  email: string | null;
  role: 'owner' | 'sub_admin' | 'user';
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string | null;
  parent_id: string | null;
  tenant_role: 'super_admin' | 'tenant_owner' | 'member' | null;
  tenant_id: string | null;
  tenant_plan: string | null;
}

export interface LoginRequest {
  username_or_email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export interface CreateUserRequest {
  username: string;
  email?: string;
  password: string;
  role: 'sub_admin' | 'user';
}

export interface UpdateUserRequest {
  role?: 'sub_admin' | 'user';
  is_active?: boolean;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  resource: string | null;
  ip: string | null;
  user_agent: string | null;
  success: boolean;
  created_at: string | null;
  username: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function authHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Login failed' }));
    const err = new Error(error.detail || 'Login failed') as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function refreshToken(refresh_token: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Refresh failed' }));
    throw new Error(error.detail || 'Session expired');
  }
  return res.json();
}

export async function logout(): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error('Logout failed');
}

export async function getMe(token: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to fetch user');
  return res.json();
}

export async function changePassword(token: string, data: ChangePasswordRequest): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/change-password`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to change password' }));
    throw new Error(error.detail || 'Failed to change password');
  }
}

export async function createUser(token: string, data: CreateUserRequest): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/users`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create user' }));
    throw new Error(error.detail || 'Failed to create user');
  }
  return res.json();
}

export async function listUsers(token: string): Promise<User[]> {
  const res = await fetch(`${API_BASE}/auth/users`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to fetch users');
  return res.json();
}

export async function updateUser(token: string, userId: string, data: UpdateUserRequest): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/users/${userId}`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to update user' }));
    throw new Error(error.detail || 'Failed to update user');
  }
  return res.json();
}

export async function deleteUser(token: string, userId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/users/${userId}`, { method: 'DELETE', headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to delete user');
}

export async function getAuditLogs(token: string, limit = 10): Promise<AuditLogEntry[]> {
  const res = await fetch(`${API_BASE}/auth/audit?limit=${limit}`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  return res.json();
}
