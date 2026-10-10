'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  UserCheck,
  CreditCard,
  UserPlus,
  Download,
  DollarSign,
  Server,
  Database,
  Activity,
  HardDrive,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import { getAdminStats, getSystemHealth } from '@/lib/api/admin';
import { useAuthStore } from '@/lib/store/auth';

const KPI_CARDS = [
  { key: 'total_tenants', label: 'Total Tenants', icon: Users, color: '#6C3FC5', glow: 'rgba(108, 63, 197, 0.3)' },
  { key: 'active_tenants', label: 'Active Tenants', icon: UserCheck, color: '#00FF88', glow: 'rgba(0, 255, 136, 0.3)' },
  { key: 'pending_payments', label: 'Pending Payments', icon: CreditCard, color: '#FDCB6E', glow: 'rgba(253, 203, 110, 0.3)' },
  { key: 'total_members', label: 'Total Members', icon: UserPlus, color: '#00F5FF', glow: 'rgba(0, 245, 255, 0.3)' },
  { key: 'downloads_today', label: 'Downloads Today', icon: Download, color: '#00FF88', glow: 'rgba(0, 255, 136, 0.3)' },
  { key: 'downloads_this_month', label: 'Downloads This Month', icon: TrendingUp, color: '#3D8BF8', glow: 'rgba(61, 139, 248, 0.3)' },
  { key: 'approved_revenue_this_month', label: 'Revenue This Month', icon: DollarSign, color: '#FDCB6E', glow: 'rgba(253, 203, 110, 0.3)' },
];

const HEALTH_ITEMS = [
  { key: 'backend_ok', label: 'Backend API', icon: Server, okColor: '#00FF88', failColor: '#FF6B6B' },
  { key: 'redis_ok', label: 'Redis', icon: Database, okColor: '#00FF88', failColor: '#FF6B6B' },
  { key: 'celery_ok', label: 'Celery Workers', icon: Activity, okColor: '#00FF88', failColor: '#FF6B6B' },
  { key: 'disk_free_gb', label: 'Disk Free', icon: HardDrive, okColor: '#00FF88', failColor: '#FF6B6B', isDisk: true },
];

export default function AdminOverviewPage() {
  const { accessToken } = useAuthStore();
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!accessToken) return;
      try {
        setLoading(true);
        const [statsData, healthData] = await Promise.all([
          fetch(`/api/v1/admin/stats`, { headers: { Authorization: `Bearer ${accessToken}` } }).then(r => r.json()),
          fetch(`/api/v1/admin/health`, { headers: { Authorization: `Bearer ${accessToken}` } }).then(r => r.json()),
        ]);
        setStats(statsData);
        setHealth(healthData);
      } catch (e: any) {
        setError(e.message || 'Failed to load admin data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [accessToken]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-text-secondary">
        Failed to load: {error}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-bold font-heading text-text-primary">Admin Overview</h1>
          <p className="text-text-secondary mt-1">Super admin control room — system health and key metrics</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-1 text-xs font-medium text-accent-secondary bg-accent-secondary/10 rounded-full">
            SUPER ADMIN
          </span>
        </div>
      </motion.div>

      {/* KPI Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4"
      >
        {KPI_CARDS.map((kpi, index) => (
          <motion.div
            key={kpi.key}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + index * 0.05 }}
            className="glass-card p-5 card-hover relative overflow-hidden group"
          >
            <div className="absolute top-0 right-0 w-24 h-24 rounded-full blur-[40px] opacity-20 group-hover:opacity-40 transition-opacity"
              style={{ background: kpi.color }} />
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-3">
                <div
                  className="p-2 rounded-lg"
                  style={{ backgroundColor: `${kpi.color}20`, color: kpi.color }}
                >
                  <kpi.icon className="w-5 h-5" />
                </div>
              </div>
              <p className="text-text-secondary text-xs uppercase tracking-wide mb-1">{kpi.label}</p>
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + index * 0.05 + 0.2 }}
                className="text-2xl font-bold font-heading text-text-primary"
              >
                {stats?.[kpi.key] !== undefined
                  ? kpi.key === 'approved_revenue_this_month'
                    ? `$${Number(stats[kpi.key]).toLocaleString()}`
                    : typeof stats[kpi.key] === 'number'
                      ? stats[kpi.key].toLocaleString()
                      : stats[kpi.key]
                  : '—'}
              </motion.p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Health Strip */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card p-5"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold font-heading text-text-primary flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent-secondary" />
            System Health
          </h2>
          <span className={`px-3 py-1 text-xs font-medium rounded-full ${
            health?.backend_ok && health?.redis_ok && health?.celery_ok
              ? 'text-accent-secondary bg-accent-secondary/10'
              : 'text-status-error bg-status-error/10'
          }`}>
            {health?.backend_ok && health?.redis_ok && health?.celery_ok ? 'All Systems Operational' : 'Degraded'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {HEALTH_ITEMS.map((item, index) => (
            <motion.div
              key={item.key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + index * 0.05 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-bg-tertiary/50"
            >
              <div
                className="p-3 rounded-xl"
                style={{
                  backgroundColor: `${(health?.[item.key] ? item.okColor : item.failColor) + '20'}`,
                  color: health?.[item.key] ? item.okColor : item.failColor,
                }}
              >
                <item.icon className="w-6 h-6" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-text-secondary text-xs uppercase tracking-wide mb-1">{item.label}</p>
                <p className="text-text-primary font-medium">
                  {item.isDisk
                    ? `${health?.[item.key] ?? '—'} GB`
                    : health?.[item.key]
                      ? 'Healthy'
                      : 'Unhealthy'}
                </p>
              </div>
              <div
                className={`w-3 h-3 rounded-full ${
                  health?.[item.key] ? 'bg-status-success' : 'bg-status-error'
                } animate-pulse`} />
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Downloads Chart (Simple Bar) */}
      {stats?.downloads_last_7_days && stats.downloads_last_7_days.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-5"
        >
          <h2 className="text-lg font-semibold font-heading text-text-primary mb-4">Downloads (Last 7 Days)</h2>
          <div className="flex items-end justify-center gap-3 h-48">
            {stats.downloads_last_7_days.map((day: any, index: number) => (
              <motion.div
                key={day.date}
                initial={{ opacity: 0, scaleY: 0 }}
                animate={{ opacity: 1, scaleY: 1 }}
                transition={{ delay: 0.3 + index * 0.05, duration: 0.5 }}
                className="flex flex-col items-center flex-1 max-w-[60px]"
              >
                <div
                  className="w-full rounded-t bg-gradient-to-t from-accent-primary to-accent-secondary"
                  style={{ height: `${Math.max(10, (day.count / Math.max(1, Math.max(...stats.downloads_last_7_days.map((d: any) => d.count)))) * 90)}%` }}
                />
                <p className="text-xs text-text-secondary mt-2 text-center">{day.date.slice(5)}</p>
                <p className="text-xs text-text-primary font-medium text-center">{day.count}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}