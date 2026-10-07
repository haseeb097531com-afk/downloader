'use client';

import { useEffect, useState, useMemo } from 'react';
import { AnalyticsOverview, TimelineDataPoint, CreatorStat, StorageStat } from '@/lib/api/analytics';
import { getAnalyticsOverview, getAnalyticsTimeline, getAnalyticsCreators, getAnalyticsStorage, exportAnalyticsCsv, exportAnalyticsPdf } from '@/lib/api/analytics';
import { BarChart3, TrendingUp, HardDrive, Users, Download, FileText, Calendar } from 'lucide-react';
import { motion } from 'framer-motion';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

const CHART_COLORS = ['#6C5CE7', '#00D2FF', '#FF6B6B', '#00B894', '#FD79A8', '#A29BFE'];

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [timeline, setTimeline] = useState<TimelineDataPoint[]>([]);
  const [creators, setCreators] = useState<CreatorStat[]>([]);
  const [storage, setStorage] = useState<StorageStat | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState<string | null>(null);
  const [range, setRange] = useState('7d');

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    Promise.all([
      getAnalyticsOverview(),
      getAnalyticsTimeline(range),
      getAnalyticsCreators(),
      getAnalyticsStorage(),
    ])
      .then(([ov, tl, cr, st]) => {
        if (!cancelled) {
          setOverview(ov);
          setTimeline(tl);
          setCreators(cr);
          setStorage(st);
        }
      })
      .catch((err) => {
        console.error(err);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [range]);

  const timelineChartData = useMemo(() => {
    return timeline.map((d) => ({
      date: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
      downloads: d.downloads,
      size_bytes: d.size_bytes,
    }));
  }, [timeline]);

  const creatorChartData = useMemo(() => {
    return creators.slice(0, 8).map((c, i) => ({
      name: c.username,
      count: c.count,
      color: CHART_COLORS[i % CHART_COLORS.length],
    }));
  }, [creators]);

  const storageChartData = useMemo(() => {
    if (!storage) return [];
    return [
      { name: 'Used', value: storage.used_bytes, color: '#6C5CE7' },
      { name: 'Free', value: storage.free_bytes, color: '#222230' },
    ];
  }, [storage]);

  const handleExport = async (type: 'csv' | 'pdf') => {
    setIsExporting(type);
    try {
      const fn = type === 'csv' ? exportAnalyticsCsv : exportAnalyticsPdf;
      const result = await fn(range);
      const link = document.createElement('a');
      link.href = result.url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error(err);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Analytics</h1>
          <p className="text-text-secondary">Insights and performance metrics</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-bg-tertiary border border-border rounded-lg p-1">
            {['24h', '7d', '30d', '90d'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  range === r ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white' : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <button
            onClick={() => handleExport('csv')}
            disabled={!!isExporting}
            className="px-4 py-2 rounded-lg bg-bg-tertiary border border-border text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors flex items-center gap-2 text-sm font-medium"
          >
            <FileText className="w-4 h-4" />
            Export CSV
          </button>
          <button
            onClick={() => handleExport('pdf')}
            disabled={!!isExporting}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            {isExporting === 'pdf' ? 'Exporting...' : 'Export PDF'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="glass-card rounded-xl p-6 animate-pulse">
              <div className="h-4 bg-bg-tertiary rounded w-1/2 mb-3" />
              <div className="h-8 bg-bg-tertiary rounded w-1/3" />
            </div>
          ))}
        </div>
      ) : overview ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <Download className="w-5 h-5 text-accent-primary" />
              <span className="text-text-secondary text-sm">Total Downloads</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{overview.total_downloads}</p>
          </motion.div>
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <HardDrive className="w-5 h-5 text-accent-secondary" />
              <span className="text-text-secondary text-sm">Total Storage</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{formatBytes(overview.total_size_bytes)}</p>
          </motion.div>
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <Users className="w-5 h-5 text-status-success" />
              <span className="text-text-secondary text-sm">Active Profiles</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{overview.active_profiles}</p>
          </motion.div>
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-5 h-5 text-status-warning" />
              <span className="text-text-secondary text-sm">Growth</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{formatPercent(overview.growth_percent)}</p>
          </motion.div>
        </div>
      ) : null}

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 glass-card rounded-xl p-6 animate-pulse">
            <div className="h-4 bg-bg-tertiary rounded w-1/3 mb-4" />
            <div className="h-48 bg-bg-tertiary rounded" />
          </div>
          <div className="glass-card rounded-xl p-6 animate-pulse">
            <div className="h-4 bg-bg-tertiary rounded w-1/2 mb-4" />
            <div className="h-48 bg-bg-tertiary rounded" />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 glass-card rounded-xl p-6">
            <h3 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-accent-primary" />
              Downloads Timeline
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={timelineChartData}>
                <XAxis dataKey="date" tick={{ fill: '#A0A0B0', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#A0A0B0', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(18, 18, 26, 0.9)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                />
                <Line type="monotone" dataKey="downloads" stroke="#6C5CE7" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="glass-card rounded-xl p-6">
            <h3 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-accent-secondary" />
              Top Creators
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={creatorChartData}>
                <XAxis dataKey="name" tick={{ fill: '#A0A0B0', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#A0A0B0', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(18, 18, 26, 0.9)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {creatorChartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card rounded-xl p-6 animate-pulse">
            <div className="h-4 bg-bg-tertiary rounded w-1/3 mb-4" />
            <div className="h-32 bg-bg-tertiary rounded" />
          </div>
          <div className="glass-card rounded-xl p-6 animate-pulse">
            <div className="h-4 bg-bg-tertiary rounded w-1/3 mb-4" />
            <div className="h-32 bg-bg-tertiary rounded" />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card rounded-xl p-6">
            <h3 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
              <HardDrive className="w-5 h-5 text-status-warning" />
              Storage Usage
            </h3>
            <div className="flex items-center gap-6">
              <ResponsiveContainer width="40%" height={180}>
                <PieChart>
                  <Pie
                    data={storageChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={70}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {storageChartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(18, 18, 26, 0.9)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: '8px',
                      color: '#fff',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-text-secondary text-sm">Used</span>
                    <span className="text-text-primary text-sm font-mono">{storage ? formatBytes(storage.used_bytes) : '0 B'}</span>
                  </div>
                  <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary"
                      style={{ width: storage ? `${storage.percent_used}%` : '0%' }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-text-secondary text-sm">Free</span>
                    <span className="text-text-primary text-sm font-mono">{storage ? formatBytes(storage.free_bytes) : '0 B'}</span>
                  </div>
                  <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: storage ? `${100 - storage.percent_used}%` : '0%',
                        background: '#222230',
                      }}
                    />
                  </div>
                </div>
                <p className="text-text-secondary text-sm">
                  {storage ? `${formatPercent(storage.percent_used)} of total capacity used` : '0% used'}
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <h3 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-status-info" />
              Top Creators
            </h3>
            <div className="space-y-3">
              {creators.length === 0 ? (
                <p className="text-text-secondary text-sm text-center py-8">No creator data available</p>
              ) : (
                creators.slice(0, 8).map((creator, i) => (
                  <div key={creator.username} className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary text-xs font-mono">
                      #{i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-text-primary text-sm font-medium truncate">{creator.username}</span>
                        <span className="text-text-secondary text-xs">{creator.count} downloads</span>
                      </div>
                      <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min((creator.count / (creators[0]?.count || 1)) * 100, 100)}%`,
                            background: CHART_COLORS[i % CHART_COLORS.length],
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
