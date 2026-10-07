const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getPublicKey(): Promise<{ public_key: string }> {
  const res = await fetch(`${API_BASE}/push/public-key`);
  if (!res.ok) throw new Error('Failed to fetch push public key');
  return res.json();
}

export async function subscribePush(subscription: PushSubscription): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subscription }),
  });
  if (!res.ok) throw new Error('Failed to subscribe to push');
  return res.json();
}

export async function unsubscribePush(): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/push/unsubscribe`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to unsubscribe from push');
  return res.json();
}

export async function sendTestPush(): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/push/test`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to send test push');
  return res.json();
}
