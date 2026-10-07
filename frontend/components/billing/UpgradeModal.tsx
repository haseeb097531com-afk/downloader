'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Lock, Sparkles } from 'lucide-react';
import { createCheckout, CheckoutRequest } from '@/lib/api/billing';
import { useAuthStore } from '@/lib/store/auth';
import { PLAN_LABELS } from '@/lib/constants/feature-access';

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  featureKey: string;
  neededPlan: string;
}

export function UpgradeModal({ isOpen, onClose, featureKey, neededPlan }: UpgradeModalProps) {
  const { user, accessToken } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setLoading(false);
      setError(null);
    }
  }, [isOpen]);

  const handleUpgrade = async () => {
    if (!user?.tenant_id || !accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const payload: CheckoutRequest = {
        tenant_id: user.tenant_id,
        plan: neededPlan,
      };
      const session = await createCheckout(accessToken, payload);
      if (session?.url) {
        window.open(session.url, '_blank');
        onClose();
      } else {
        setError('Checkout session could not be started.');
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to start checkout.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            className="glass-card relative z-10 w-full max-w-md rounded-2xl p-6"
            initial={{ scale: 0.95, y: 10 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.95, y: 10 }}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-text-muted hover:text-text-primary transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-primary to-accent-secondary flex items-center justify-center">
                <Lock className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-primary">Upgrade required</h3>
                <p className="text-sm text-text-secondary">
                  {featureKey.replace(/_/g, ' ')} requires the <span className="font-medium text-accent-primary">{PLAN_LABELS[neededPlan] || neededPlan}</span> plan.
                </p>
              </div>
            </div>

            <p className="text-sm text-text-secondary mb-6">
              Unlock this feature and get higher quotas, priority support, and advanced controls.
            </p>

            {error && (
              <p className="text-sm text-status-error mb-4">{error}</p>
            )}

            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {loading ? (
                'Starting checkout...'
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Upgrade to {PLAN_LABELS[neededPlan] || neededPlan}
                </>
              )}
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

