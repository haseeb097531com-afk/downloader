const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export interface AnalysisStatus {
  status: 'none' | 'processing' | 'completed' | 'failed';
  language: string | null;
  transcript_text: string | null;
  summary_text: string | null;
  keywords: string[];
  translated: Record<string, string>;
  error: string | null;
}

export async function getAnalysis(downloadId: string): Promise<AnalysisStatus> {
  const res = await fetch(`${API_BASE}/analysis/${downloadId}`);
  if (!res.ok) throw new Error('Failed to fetch analysis');
  return res.json();
}

export async function runAnalysis(downloadId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/analysis/${downloadId}/run`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start analysis');
  return res.json();
}

export async function translateAnalysis(downloadId: string, lang: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/analysis/${downloadId}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lang }),
  });
  if (!res.ok) throw new Error('Failed to request translation');
  return res.json();
}

export async function getAnalysisContent(downloadId: string, kind: string): Promise<{ content: string }> {
  const res = await fetch(`${API_BASE}/analysis/${downloadId}/content/${kind}`);
  if (!res.ok) throw new Error(`Failed to fetch ${kind} content`);
  return res.json();
}

