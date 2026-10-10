'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store/auth';
import { listAdminPayments, approveAdminPayment, rejectAdminPayment, AdminPayment } from '@/lib/api/admin';
import { Shield, Loader2, CreditCard, CheckCircle2, AlertCircle, Eye, AlertTriangle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const STATUS_COLORS = {
  pending: { bg: 'bg-status-warning/10', text: 'text-status-warning', icon: AlertTriangle },
  approved: { bg: 'bg-status-success/10', text: 'text-status-success', icon: CheckCircle2 },
  rejected: { bg: 'bg-status-error/10', text: 'text-status-error', icon: AlertCircle },
};

export default function AdminPaymentsPage() {
  const { user, accessToken } = useAuthStore();
  const isSuperAdmin = user?.is_super_admin;

  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all');
  const [selectedPayment, setSelectedPayment] = useState<AdminPayment | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !isSuperAdmin) return;
    let cancelled = false;
    const fetchPayments = async () => {
      try {
        setLoading(true);
        const data = await fetch(`/api/v1/admin/payments`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        }).then(r => r.json());
        if (!cancelled) setPayments(data);
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Failed to load payments');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchPayments();
    return () => { cancelled = true; };
  }, [accessToken, isSuperAdmin]);

  const handleApprove = async (payment: AdminPayment) => {
    if (!accessToken) return;
    setActionLoading(payment.id);
    try {
      await approveAdminPayment(accessToken, payment.id);
      setPayments(prev => prev.map(p => p.id === payment.id ? { ...p, status: 'approved' } : p));
      setSelectedPayment(null);
    } catch (e: any) {
      alert(e.message || 'Failed to approve payment');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (payment: AdminPayment) => {
    const reason = prompt('Reason for rejection (optional):');
    if (reason === null) return; // User cancelled
    if (!accessToken) return;
    setActionLoading(payment.id);
    try {
      await rejectAdminPayment(accessToken, payment.id, reason || undefined);
      setPayments(prev => p => p.id === payment.id ? { ...p, status: 'rejected' } : p);
      setSelectedPayment(null);
    } catch (e: any) {
      alert(e.message || 'Failed to reject payment');
    } finally {
      setActionLoading(null);
    }
  };

  if (!isSuperAdmin) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-text-secondary">Super admin access required.</p>
      </div>
    );
  }

  const filteredPayments = statusFilter === 'all'
    ? payments
    : payments.filter(p => p.status === statusFilter);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <motion.div className="w-6 h-6 animate-spin text-accent-primary" animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
          </svg>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-accent-primary" />
          <h1 className="text-2xl font-bold">Payments</h1>
          <span className="px-3 py-1 text-xs font-medium text-accent-secondary bg-accent-secondary/10 rounded-full">
            Super Admin
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'pending', 'approved', 'rejected'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                statusFilter === status
                  ? 'bg-accent-primary text-white'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50'
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-3 rounded-xl bg-status-error/10 text-status-error text-sm flex items-center gap-2"
        >
          <AlertTriangle className="w-4 h-4" /> {error}
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card overflow-hidden"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-primary">
                <th className="text-left p-4 font-medium text-text-secondary">ID</th>
                <th className="text-left p-4 font-medium text-text-secondary">Tenant</th>
                <th className="text-left p-4 font-medium text-text-secondary">Plan</th>
                <th className="text-left p-4 font-medium text-text-secondary">Amount</th>
                <th className="text-left p-4 font-medium text-text-secondary">Reference</th>
                <th className="text-left p-4 font-medium text-text-secondary">Status</th>
                <th className="text-left p-4 font-medium text-text-secondary">Date</th>
                <th className="text-left p-4 font-medium text-text-secondary">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredPayments.map((p) => {
                const statusConfig = STATUS_COLORS[p.status as keyof typeof STATUS_COLORS] || STATUS_COLORS.pending;
                const Icon = statusConfig.icon;
                return (
                  <motion.tr
                    key={p.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.05 }}
                    className="border-b border-border-primary/50 hover:bg-bg-secondary/30"
                  >
                    <td className="p-4 font-mono text-xs text-text-secondary">{p.id}</td>
                    <td className="p-4">
                      <div className="font-medium">{p.tenant_name}</div>
                      <div className="text-xs text-text-secondary">{p.tenant_id}</div>
                    </td>
                    <td className="p-4">
                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-accent-primary/10 text-accent-primary">
                        {p.plan}
                      </span>
                    </td>
                    <td className="p-4 font-medium">${p.amount.toFixed(2)}</td>
                    <td className="p-4 text-text-secondary text-xs">{p.reference}</td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusConfig.bg} ${statusConfig.text} flex items-center gap-1`}>
                        <Icon className="w-3 h-3" />
                        {p.status.charAt(0).toUpperCase() + p.status.slice(1)}
                      </span>
                    </td>
                    <td className="p-4 text-text-secondary">{p.created_at ? new Date(p.created_at).toLocaleString() : '-'}</td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedPayment(p)}
                          className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50 transition-colors"
                          title="View details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {p.status === 'pending' && (
                          <>
                            <button
                              onClick={() => handleApprove(p)}
                              disabled={actionLoading === p.id}
                              className="px-3 py-1.5 rounded-lg bg-status-success/10 text-status-success text-xs hover:bg-status-success/20 disabled:opacity-50 flex items-center gap-1"
                            >
                              <CheckCircle2 className="w-3 h-3" />
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(p)}
                              disabled={actionLoading === p.id}
                              className="px-3 py-1.5 rounded-lg bg-status-error/10 text-status-error text-xs hover:bg-status-error/20 disabled:opacity-50 flex items-center gap-1"
                            >
                              <AlertCircle className="w-3 h-3" />
                              Reject
                            </button>
                          </>
                        }
                        {actionLoading === p.id && (
                          <motion.div className="w-4 h-4 animate-spin text-text-secondary" animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                              <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                            </svg>
                          </motion.div>
                        )}
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
              {filteredPayments.length === 0 && (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-text-secondary">No payments found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Payment Detail Modal */}
      <AnimatePresence>
        {selectedPayment && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
            onClick={() => setSelectedPayment(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-bg-secondary rounded-2xl p-6 max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">Payment Details</h2>
                <button
                  onClick={() => setSelectedPayment(null)}
                  className="p-2 rounded-lg hover:bg-bg-tertiary/50 transition-colors"
                >
                  <AlertCircle className="w-5 h-5" />
                </button>
              </div>
              <div className="space-y-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Payment ID</span>
                  <span className="font-mono text-xs">{selectedPayment.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Tenant</span>
                  <span className="font-medium">{selectedPayment.tenant_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Tenant ID</span>
                  <span className="font-mono text-xs">{selectedPayment.tenant_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Plan</span>
                  <span className="px-2 py-1 rounded-full text-xs font-medium bg-accent-primary/10 text-accent-primary">
                    {selectedPayment.plan}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Amount</span>
                  <span className="font-bold">${selectedPayment.amount.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Reference</span>
                  <span className="font-mono text-xs">{selectedPayment.reference}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Status</span>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[selectedPayment.status as keyof typeof STATUS_COLORS].bg} ${STATUS_COLORS[selectedPayment.status as keyof typeof STATUS_COLORS].text} flex items-center gap-1`}>
                    <STATUS_COLORS[selectedPayment.status as keyof typeof STATUS_COLORS].icon className="w-3 h-3" />
                    {selectedPayment.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Date</span>
                  <span>{selectedPayment.created_at ? new Date(selectedPayment.created_at).toLocaleString() : '-'}</span>
                </div>
                {selectedPayment.screenshot_url && (
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Screenshot</span>
                    <a href={selectedPayment.screenshot_url} target="_blank" rel="noopener noreferrer" className="text-accent-primary hover:underline text-sm">
                      View
                    </a>
                  </div>
                )}
              </div>
              <div className="flex gap-3 mt-6 pt-4 border-t border-border-primary">
                {selectedPayment.status === 'pending' && (
                  <>
                    <button
                      onClick={() => handleApprove(selectedPayment)}
                      disabled={actionLoading === selectedPayment.id}
                      className="flex-1 px-4 py-2 rounded-lg bg-status-success/10 text-status-success hover:bg-status-success/20 disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(selectedPayment)}
                      disabled={actionLoading === selectedPayment.id}
                      className="flex-1 px-4 py-2 rounded-lg bg-status-error/10 text-status-error hover:bg-status-error/20 disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      <AlertCircle className="w-4 h-4" />
                      Reject
                    </button>
                  </>
                }}
                <button
                  onClick={() => setSelectedPayment(null)}
                  className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50 transition-colors"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}