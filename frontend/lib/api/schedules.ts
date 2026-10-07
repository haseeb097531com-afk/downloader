export interface Schedule {
  id: string;
  profile_id: string | null;
  frequency: 'daily' | 'weekly' | 'cron';
  cron_expression: string | null;
  time_of_day: string;
  days_of_week: string[] | null;
  quality: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateScheduleRequest {
  profile_id?: string | null;
  frequency: 'daily' | 'weekly' | 'cron';
  time_of_day: string;
  days_of_week?: string[] | null;
  cron_expression?: string | null;
  quality?: string;
  is_active?: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function listSchedules(): Promise<Schedule[]> {
  const res = await fetch(`${API_BASE}/schedules`);
  if (!res.ok) throw new Error('Failed to fetch schedules');
  return res.json();
}

export async function getSchedule(id: string): Promise<Schedule> {
  const res = await fetch(`${API_BASE}/schedules/${id}`);
  if (!res.ok) throw new Error('Failed to fetch schedule');
  return res.json();
}

export async function createSchedule(payload: CreateScheduleRequest): Promise<Schedule> {
  const res = await fetch(`${API_BASE}/schedules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create schedule');
  return res.json();
}

export async function updateSchedule(id: string, payload: Partial<CreateScheduleRequest>): Promise<Schedule> {
  const res = await fetch(`${API_BASE}/schedules/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update schedule');
  return res.json();
}

export async function deleteSchedule(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/schedules/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete schedule');
}
