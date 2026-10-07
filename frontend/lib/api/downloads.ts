import { DuplicateMatch } from './dedup';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export interface CreateDownloadRequest {
  url: string;
  start_time?: string;
  end_time?: string;
}

export interface CreateDownloadResponse {
  id: string;
  status: string;
  message: string;
}

export class DuplicateError extends Error {
  matches: DuplicateMatch[];
  constructor(matches: DuplicateMatch[]) {
    super('Duplicate detected');
    this.matches = matches;
    this.name = 'DuplicateError';
  }
}

export async function createDownload(data: CreateDownloadRequest, force = false): Promise<CreateDownloadResponse> {
  const res = await fetch(`${API_BASE}/downloads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...data, force }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    if (res.status === 409 && error.matches) {
      const err = new Error('Duplicate detected') as DuplicateError;
      err.matches = error.matches as DuplicateMatch[];
      throw err;
    }
    throw new Error('Failed to create download');
  }
  return res.json();
}

