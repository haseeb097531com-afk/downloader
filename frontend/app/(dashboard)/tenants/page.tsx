'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store/auth';
import { listTenants, changeTenantPlan, setTenantExpiry, waiveTenantQuota, BillingTenant } from '@/lib/api/billing';
import { Shield, Loader2, Crown, CalendarClock, Wand2, AlertCircle } from 'lucide-react';

const PLAN_OPTIONS = [
  { value: 'trial', label: 'Trial' },
  { value: 'starter', label: 'Starter' },
  { value: 'pro', label: 'Pro' },
  { value: 'enterprise', label: 'Enterprise' },
];

export default function TenantsPage() {
  const { user, accessToken } = useAuthStore();
  const isSuperAdmin = user?.role === 'owner' && user?.tenant_role === 'super_admin';

  const [tenants, setTenants] = useState<BillingTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [waiving, setWaiving] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !isSuperAdmin) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await listTenants(accessToken);
        if (!cancelled) setTenants(data);
      } catch (e) {
        console.error('Failed to load tenants', e);
        if (!cancelled) setError('Failed to load tenants');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [accessToken, isSuperAdmin]);

  const handlePlanChange = async (tenantId: string, plan: string) => {
    if (!accessToken) return;
    try {
      await changeTenantPlan(accessToken, tenantId, plan);
      setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, plan } : t)));
    } catch (e: any) {
      alert(e?.message || 'Failed to change plan');
    }
  };

  const handleExpiry = async (tenantId: string, plan_expires_at: string | null, auto_renew: boolean) => {
    if (!accessToken) return;
    try {
      const updated = await setTenantExpiry(accessToken, tenantId, plan_expires_at, auto_renew);
      setTenants((prev) => prev.map((t) => (t.id === tenantId ? updated : t)));
    } catch (e: any) {
      alert(e?.message || 'Failed to set expiry');
    }
  };

  const handleWaive = async (tenantId: string) => {
    if (!accessToken) return;
    setWaiving(tenantId);
    try {
      const updated = await waiveTenantQuota(accessToken, tenantId, 24);
      setTenants((prev) => prev.map((t) => (t.id === tenantId ? updated : t)));
    } catch (e: any) {
      alert(e?.message || 'Failed to waive quota');
    } finally {
      setWaiving(null);
    }
  };

  if (!isSuperAdmin) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-text-secondary">Super admin access required.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-accent-primary" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Shield className="w-6 h-6 text-accent-primary" />
        <h1 className="text-2xl font-bold">Tenants</h1>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-status-error/10 text-status-error text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="glass-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-primary">
              <th className="text-left p-4 font-medium text-text-secondary">Name</th>
              <th className="text-left p-4 font-medium text-text-secondary">Slug</th>
              <th className="text-left p-4 font-medium text-text-secondary">Plan</th>
              <th className="text-left p-4 font-medium text-text-secondary">Expires</th>
              <th className="text-left p-4 font-medium text-text-secondary">Auto-renew</th>
              <th className="text-left p-4 font-medium text-text-secondary">Override</th>
              <th className="text-left p-4 font-medium text-text-secondary">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id} className="border-b border-border-primary/50 hover:bg-bg-secondary/30">
                <td className="p-4 font-medium">{t.name}</td>
                <td className="p-4 text-text-secondary">{t.slug}</td>
                <td className="p-4">
                  <select
                    value={t.plan}
                    onChange={(e) => handlePlanChange(t.id, e.target.value)}
                    className="bg-bg-tertiary border border-border-primary rounded-lg px-2 py-1 text-xs"
                  >
                    {PLAN_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </td>
                <td className="p-4">
                  <input
                    type="date"
                    value={t.plan_expires_at ? t.plan_expires_at.slice(0, 10) : ''}
                    onChange={(e) => handleExpiry(t.id, e.target.value ? new Date(e.target.value).toISOString() : null, t.auto_renew)}
                    className="bg-bg-tertiary border border-border-primary rounded-lg px-2 py-1 text-xs w-36"
                  />
                </td>
                <td className="p-4">
                  <input
                    type="checkbox"
                    checked={t.auto_renew}
                    onChange={(e) => handleExpiry(t.id, t.plan_expires_at, e.target.checked)}
                    className="rounded"
                  />
                </td>
                <td className="p-4 text-xs text-text-secondary">
                  {t.quota_override_until ? new Date(t.quota_override_until).toLocaleString() : '-'}
                </td>
                <td className="p-4">
                  <button
                    onClick={() => handleWaive(t.id)}
                    disabled={waiving === t.id}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-accent-primary/10 text-accent-primary text-xs hover:bg-accent-primary/20 disabled:opacity-50"
                  >
                    {waiving === t.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Wand2 className="w-3 h-3" />
                    )}
                    Waive 24h
                  </button>
                </td>
              </tr>
            ))}
            {tenants.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-text-secondary">No tenants found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
