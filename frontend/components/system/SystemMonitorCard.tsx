'use client';

import { useEffect, useState } from 'react';
import { getSystemStats, SystemStats } from '@/lib/api/system';
import { Cpu, HardDrive, CheckCircle2, AlertTriangle } from 'lucide-react';

export function SystemMonitorCard() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const data = await getSystemStats();
        if (mounted) {
          setStats(data);
        }
      } catch (e) {
        console.error(e);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 3000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const getStatusColor = (percent: number) => {
    if (percent < 70) return 'text-status-success';
    if (percent < 90) return 'text-status-warning';
    return 'text-status-error';
  };

  const getBarColor = (percent: number) => {
    if (percent < 70) return 'bg-status-success';
    if (percent < 90) return 'bg-status-warning';
    return 'text-status-error';
  };

  if (isLoading) {
    return (
      <div className="glass-card rounded-lg p-4 animate-pulse">
        <div className="h-3 bg-bg-tertiary rounded w-1/4 mb-3" />
        <div className="space-y-2.5">
          <div className="h-2 bg-bg-tertiary rounded w-full" />
          <div className="h-2 bg-bg-tertiary rounded w-full" />
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="glass-card rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide">System</h3>
        {stats.is_throttled ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-status-warning">
            <AlertTriangle className="w-3 h-3" />
            Throttled
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] text-status-success">
            <CheckCircle2 className="w-3 h-3" />
            Normal
          </span>
        )}
      </div>

      <div className="space-y-3">
        {/* CPU */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <Cpu className={`w-3.5 h-3.5 ${getStatusColor(stats.cpu_percent)}`} />
              <span className="text-xs text-text-secondary">CPU</span>
            </div>
            <span className={`text-xs font-medium tabular-nums ${getStatusColor(stats.cpu_percent)}`}>
              {stats.cpu_percent.toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${getBarColor(stats.cpu_percent)}`}
              style={{ width: `${Math.min(stats.cpu_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* RAM */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <HardDrive className={`w-3.5 h-3.5 ${getStatusColor(stats.ram_percent)}`} />
              <span className="text-xs text-text-secondary">RAM</span>
            </div>
            <span className={`text-xs font-medium tabular-nums ${getStatusColor(stats.ram_percent)}`}>
              {stats.ram_percent.toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${getBarColor(stats.ram_percent)}`}
              style={{ width: `${Math.min(stats.ram_percent, 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
