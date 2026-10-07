export interface LibraryItem {
  id: string;
  title: string;
  platform: string;
  content_type: string;
  file_path: string;
  file_size: number;
  exists_on_disk: boolean;
  created_at: string;
  completed_at: string | null;
  thumbnail_url: string | null;
  thumbnail_local: string | null;
  duration: number | null;
  is_watermark_free: boolean;
  metadata_json: Record<string, unknown> | null;
  status: string;
  progress: number;
  processed: boolean;
  category: string | null;
  cloud_backed_up: boolean;
  cloud_url: string | null;
  trim_start: string | null;
  trim_end: string | null;
  analysis_status: string | null;
}

export interface LibraryPage {
  items: LibraryItem[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  has_next: boolean;
}

export interface PlatformStat {
  platform: string;
  count: number;
  total_size: number;
}

export interface DailyDownloadCount {
  date: string;
  count: number;
}

export interface CreatorStat {
  username: string;
  count: number;
}

export interface LibraryStats {
  total_files: number;
  total_size_bytes: number;
  missing_files: number;
  platform_breakdown: PlatformStat[];
  downloads_last_7_days: DailyDownloadCount[];
  top_creators: CreatorStat[];
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface UntrackedFile {
  path: string;
  filename: string;
  extension: string;
  file_size: number;
  modified_at: string;
  platform: string;
  content_type: string;
  modified_since_sync: boolean;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  total_size_bytes: number;
  errors: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getLibrary(page = 1, limit = 24, platform?: string, search?: string, category?: string): Promise<LibraryPage> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (platform) params.set('platform', platform);
  if (search) params.set('search', search);
  if (category) params.set('category', category);
  const res = await fetch(`${API_BASE}/library?${params}`);
  if (!res.ok) throw new Error('Failed to fetch library');
  return res.json();
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const res = await fetch(`${API_BASE}/library/stats`);
  if (!res.ok) throw new Error('Failed to fetch library stats');
  return res.json();
}

export async function getCategories(): Promise<CategoryCount[]> {
  const res = await fetch(`${API_BASE}/library/categories`);
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

export async function renameLibraryItem(id: string, newName: string): Promise<LibraryItem> {
  const res = await fetch(`${API_BASE}/library/${id}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_name: newName }),
  });
  if (!res.ok) throw new Error('Failed to rename file');
  return res.json();
}

export async function deleteLibraryItem(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/library/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete file');
}

export async function openLibraryFolder(id: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/library/${id}/open-folder`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to open folder');
  return res.json();
}

export async function getUntrackedFiles(): Promise<UntrackedFile[]> {
  const res = await fetch(`${API_BASE}/library/untracked`);
  if (!res.ok) throw new Error('Failed to fetch untracked files');
  return res.json();
}

export async function importUntrackedFiles(filePaths: string[]): Promise<ImportResult> {
  const res = await fetch(`${API_BASE}/library/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_paths: filePaths }),
  });
  if (!res.ok) throw new Error('Failed to import files');
  return res.json();
}
