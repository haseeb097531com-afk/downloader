export const FEATURE_ACCESS: Record<string, string> = {
  home: 'all',
  library: 'all',
  queue: 'all',
  search: 'all',
  collections: 'starter',
  profiles: 'starter',
  remote: 'starter',
  analytics_basic: 'all',
  analytics_full: 'pro',
  plugins: 'pro',
  safety: 'pro',
  team: 'tenant_owner',
  tenants: 'super_admin',
};

export const PLAN_TIERS: Record<string, number> = {
  trial: 0,
  starter: 1,
  pro: 2,
  enterprise: 3,
};

export const PLAN_LABELS: Record<string, string> = {
  trial: 'Trial',
  starter: 'Starter',
  pro: 'Pro',
  enterprise: 'Enterprise',
};

export function isFeatureUnlocked(
  featureKey: string,
  currentPlan: string | null | undefined,
): boolean {
  if (!currentPlan) return false;
  const needed = FEATURE_ACCESS[featureKey];
  if (!needed || needed === 'all') return true;
  const currentTier = PLAN_TIERS[currentPlan] ?? 0;
  const neededTier = PLAN_TIERS[needed] ?? 0;
  return currentTier >= neededTier;
}
