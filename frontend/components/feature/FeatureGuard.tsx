'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store/auth';
import { FEATURE_ACCESS, isFeatureUnlocked } from '@/lib/constants/feature-access';
import { Lock } from 'lucide-react';
import { motion } from 'framer-motion';
import { UpgradeModal } from '@/components/billing/UpgradeModal';

interface FeatureGuardProps {
  featureKey: string;
  children: React.ReactNode;
}

export function FeatureGuard({ featureKey, children }: FeatureGuardProps) {
  const { user } = useAuthStore();
  const [locked, setLocked] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const currentPlan = user?.tenant_plan || 'trial';
  const neededPlan = FEATURE_ACCESS[featureKey] || 'starter';

  useEffect(() => {
    if (!isFeatureUnlocked(featureKey, currentPlan)) {
      setLocked(true);
    }
  }, [featureKey, currentPlan]);

  if (locked) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center max-w-md"
        >
          <div className="w-16 h-16 rounded-full bg-accent-primary/20 flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8 text-accent-primary" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary mb-2">Locked</h1>
          <p className="text-text-secondary mb-6">
            This feature requires a higher plan. Upgrade to unlock it.
          </p>
          <button
            onClick={() => setUpgradeOpen(true)}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity"
          >
            Upgrade now
          </button>
          <UpgradeModal
            isOpen={upgradeOpen}
            onClose={() => setUpgradeOpen(false)}
            featureKey={featureKey}
            neededPlan={neededPlan}
          />
        </motion.div>
      </div>
    );
  }

  return <>{children}</>;
}
