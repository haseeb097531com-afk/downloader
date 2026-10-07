export interface PluginInfo {
  name: string;
  version: string;
  author: string;
  platform: string;
  status: 'active' | 'disabled';
}

export interface PluginsResponse {
  core: PluginInfo[];
  user: PluginInfo[];
}

export interface InstallPluginRequest {
  repo_url: string;
}

export interface InstallPluginResponse {
  message: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getPlugins(): Promise<PluginsResponse> {
  const res = await fetch(`${API_BASE}/plugins`);
  if (!res.ok) throw new Error('Failed to fetch plugins');
  return res.json();
}

export async function installPlugin(repoUrl: string): Promise<InstallPluginResponse> {
  const res = await fetch(`${API_BASE}/plugins/install`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Failed to install plugin' }));
    throw new Error(error.message || 'Failed to install plugin');
  }
  return res.json();
}

export async function uninstallPlugin(name: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/plugins/uninstall/${encodeURIComponent(name)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Failed to uninstall plugin' }));
    throw new Error(error.message || 'Failed to uninstall plugin');
  }
  return res.json();
}

export async function reloadPlugins(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/plugins/reload`, { method: 'POST' });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Failed to reload plugins' }));
    throw new Error(error.message || 'Failed to reload plugins');
  }
  return res.json();
}
