'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store/auth';
import { getPlans, createCheckout, listTenants, BillingTenant } from '@/lib/api/billing';
import { CreditCard, Users, Download, HardDrive, ArrowUpRight, Loader2, Crown } from 'lucide-react';

const PLAN_META: Record<string, { label: string; price: string; color: string }> = {
  trial: { label: 'Trial', price: '$0', color: 'bg-gray-500' },
  starter: { label: 'Starter', price: '$9', color: 'bg-blue-500' },
  pro: { label: 'Pro', price: '$29', color: 'bg-accent-primary' },
  enterprise: { label: 'Enterprise', price: 'Contact', color: 'bg-gradient-to-r from-accent-primary to-accent-secondary' },
};

export default function TeamPage() {
  const { user, accessToken } = useAuthStore();
  const tenantId = user?.tenant_id;
  const isOwner = user?.tenant_role === 'tenant_owner' || user?.role === 'owner';

  const [plans, setPlans] = useState<Record<string, any>>({});
  const [tenant, setTenant] = useState<BillingTenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId || !accessToken) return;
    let cancelled = false;
    (async () => {
      try {
        const [plansData, tenantsData] = await Promise.all([
          getPlans(accessToken),
          listTenants(accessToken),
        ]);
        if (!cancelled) {
          setPlans(plansData.plans);
          const current = tenantsData.find((t) => t.id === tenantId);
          setTenant(current || null);
        }
      } catch (e) {
        console.error('Failed to load billing', e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [tenantId, accessToken]);

  const handleUpgrade = async (plan: string) => {
    if (!tenantId || !accessToken) return;
    setUpgrading(true);
    setError(null);
    try {
      const session = await createCheckout(accessToken, { tenant_id: tenantId, plan });
      alert(`Contact sales / configure billing.\nSession: ${session.session_id}`);
    } catch (e: any) {
      setError(e?.message || 'Upgrade failed');
    } finally {
      setUpgrading(false);
    }
  };

  if (!isOwner) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-text-secondary">Billing is only available for tenant owners.</p>
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

  if (!tenant) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-text-secondary">No tenant information found.</p>
      </div>
    );
  }

  const planKey = tenant.plan;
  const planInfo = PLAN_META[planKey] || PLAN_META.trial;
  const limits = plans[planKey] || plans['trial'];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <CreditCard className="w-6 h-6 text-accent-primary" />
        <h1 className="text-2xl font-bold">Billing & Subscription</h1>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-status-error/10 text-status-error text-sm">{error}</div>
      )}

      {/* Current Plan Card */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${planInfo.color} flex items-center justify-center`}>
              <Crown className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-semibold text-lg">{planInfo.label} Plan</p>
              <p className="text-sm text-text-secondary">{planInfo.price}/month</p>
            </div>
          </div>
          <span className="text-xs px-2 py-1 rounded-full bg-bg-tertiary text-text-secondary capitalize">
            {tenant.status}
          </span>
        </div>

        {tenant.plan_expires_at && (
          <p className="text-xs text-text-secondary mb-4">
            Expires: {new Date(tenant.plan_expires_at).toLocaleDateString()}
          </p>
        )}

        <div className="grid grid-cols-3 gap-4">
          <UsageBar icon={Users} label="Members" used={0} limit={limits?.members ?? -1} />
          <UsageBar icon={Download} label="Downloads" used={0} limit={limits?.downloads_per_month ?? -1} />
          <UsageBar icon={HardDrive} label="Storage (GB)" used={0} limit={limits?.storage_gb ?? -1} />
        </div>
      </div>

      {/* Upgrade */}
      <div className="glass-card p-6">
        <h2 className="font-semibold mb-4">Upgrade Plan</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Object.entries(PLAN_META).map(([key, meta]) => (
            <button
              key={key}
              onClick={() => handleUpgrade(key)}
              disabled={upgrading || planKey === key}
              className={`p-4 rounded-xl border border-border-primary text-center transition-all hover:border-accent-primary disabled:opacity-50 disabled:cursor-not-allowed ${planKey === key ? 'ring-2 ring-accent-primary' : ''}`}
            >
              <p className="font-semibold">{meta.label}</p>
              <p className="text-xs text-text-secondary">{meta.price}/mo</p>
            </button>
          ))}
        </div>
        <p className="text-xs text-text-muted mt-3">
          Clicking a plan opens a stub checkout. Configure a real payment provider to activate payments.
        </p>
      </div>
    </div>
  );
}

function UsageBar({ icon: Icon, label, used, limit }: { icon: any; label: string; used: number; limit: number }) {
  const isUnlimited = limit === -1;
  const pct = isUnlimited ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const color = pct >= 90 ? 'bg-status-error' : pct >= 70 ? 'bg-status-warning' : 'bg-status-success';

  return (
    <div className="p-3 rounded-xl bg-bg-secondary/50">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-text-secondary" />
        <span className="text-xs text-text-secondary">{label}</span>
      </div>
      <p className="text-sm font-medium mb-1">
        {used} / {isUnlimited ? '∞' : limit}
      </p>
      {!isUnlimited && (
        <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

