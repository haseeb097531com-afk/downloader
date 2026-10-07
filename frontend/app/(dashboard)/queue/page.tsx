'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useQueueStore } from '@/lib/store/queue';
import { Play, Pause, X, RotateCcw, Star, Trash2, Wifi, WifiOff, Activity, Clock, CheckCircle, AlertCircle, Loader2, TriangleAlert } from 'lucide-react';
import { motion } from 'framer-motion';

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'bg-platform-youtube',
  tiktok: 'bg-platform-tiktok',
  instagram: 'bg-platform-instagram',
  facebook: 'bg-platform-facebook',
  twitter: 'bg-platform-twitter',
  whatsapp: 'bg-platform-whatsapp',
};

function formatSpeed(bytesPerSec: number | null): string {
  if (!bytesPerSec) return '0 MB/s';
  return (bytesPerSec / 1024 / 1024).toFixed(1) + ' MB/s';
}

function formatEta(seconds: number | null): string {
  if (!seconds) return '--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export default function QueuePage() {
  const {
    snapshot,
    isLoading,
    isPausingAll,
    isResumingAll,
    fetchQueue,
    prioritize,
    pauseAll,
    resumeAll,
    pause,
    resume,
    cancel,
    retry,
  } = useQueueStore();

  const [wsConnected, setWsConnected] = useState(false);
  const [failedOpen, setFailedOpen] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetchQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
    const ws = new WebSocket(`${wsUrl}/queue`);
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);
    ws.onmessage = () => {
      fetchQueue();
    };

    return () => {
      ws.close();
    };
  }, [fetchQueue]);

  const handlePauseAll = async () => {
    await pauseAll();
  };

  const handleResumeAll = async () => {
    await resumeAll();
  };

  const todayCompleted = useCallback(() => {
    if (!snapshot) return 0;
    const today = new Date().toISOString().split('T')[0];
    return snapshot.completed.filter((item) => {
      if (!item.created_at) return false;
      return item.created_at.startsWith(today);
    }).length;
  }, [snapshot]);

  return (
    <div className="max-w-7xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Download Queue</h1>
          <p className="text-text-secondary">Monitor and manage your active downloads</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${wsConnected ? 'bg-status-success/20 text-status-success' : 'bg-status-error/20 text-status-error'}`}>
            {wsConnected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
            <span className="text-sm font-medium">{wsConnected ? 'Live' : 'Offline'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-4">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-accent-primary" />
            <div>
              <p className="text-text-secondary text-xs">Active</p>
              <p className="text-2xl font-bold text-text-primary">{snapshot?.active_count ?? 0}</p>
            </div>
          </div>
        </motion.div>
        <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-4">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-status-warning" />
            <div>
              <p className="text-text-secondary text-xs">Queued</p>
              <p className="text-2xl font-bold text-text-primary">{snapshot?.queued_count ?? 0}</p>
            </div>
          </div>
        </motion.div>
        <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-4">
          <div className="flex items-center gap-3">
            <Pause className="w-5 h-5 text-status-paused" />
            <div>
              <p className="text-text-secondary text-xs">Paused</p>
              <p className="text-2xl font-bold text-text-primary">{snapshot?.paused_count ?? 0}</p>
            </div>
          </div>
        </motion.div>
        <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-4">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-status-success" />
            <div>
              <p className="text-text-secondary text-xs">Completed Today</p>
              <p className="text-2xl font-bold text-text-primary">{todayCompleted()}</p>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="flex gap-3 mb-8">
        <button
          onClick={handlePauseAll}
          disabled={isPausingAll || (snapshot?.active_count ?? 0) === 0}
          className="px-6 py-2.5 rounded-lg bg-status-paused text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
        >
          <Pause className="w-4 h-4" />
          Pause All
        </button>
        <button
          onClick={handleResumeAll}
          disabled={isResumingAll || (snapshot?.paused_count ?? 0) === 0}
          className="px-6 py-2.5 rounded-lg bg-status-success text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
        >
          <Play className="w-4 h-4" />
          Resume All
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="glass-card rounded-xl p-6 animate-pulse">
              <div className="h-6 bg-bg-tertiary rounded w-1/3 mb-4" />
              <div className="h-4 bg-bg-tertiary rounded w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {snapshot && snapshot.active.length > 0 && (
            <section>
              <h2 className="text-text-primary text-xl font-semibold mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-accent-primary" />
                Active Downloads
              </h2>
              <div className="space-y-4">
                {snapshot.active.map((item) => (
                  <ActiveDownloadCard key={item.id} item={item} onPause={pause} onResume={resume} onCancel={cancel} />
                ))}
              </div>
            </section>
          )}

          {snapshot && snapshot.queued.length > 0 && (
            <section>
              <h2 className="text-text-primary text-xl font-semibold mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5 text-status-warning" />
                Queued
              </h2>
              <div className="glass-card rounded-xl overflow-hidden">
                {snapshot.queued.map((item, index) => (
                  <QueuedItem key={item.id} item={item} index={index} onPrioritize={prioritize} onCancel={cancel} />
                ))}
              </div>
            </section>
          )}

          {snapshot && snapshot.paused.length > 0 && (
            <section>
              <h2 className="text-text-primary text-xl font-semibold mb-4 flex items-center gap-2">
                <Pause className="w-5 h-5 text-status-paused" />
                Paused
              </h2>
              <div className="glass-card rounded-xl overflow-hidden">
                {snapshot.paused.map((item) => (
                  <div key={item.id} className="flex items-center gap-4 p-4 border-b border-border last:border-b-0">
                    <div className="flex-1">
                      <p className="text-text-primary font-medium">{item.title}</p>
                      <p className="text-text-secondary text-sm capitalize">{item.platform}</p>
                    </div>
                    <button
                      onClick={() => resume(item.id)}
                      className="p-2 rounded-lg bg-status-success/20 text-status-success hover:bg-status-success hover:text-white transition-colors"
                      title="Resume"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}

          {snapshot && snapshot.active.filter((item) => item.status === 'processing').length > 0 && (
            <section>
              <h2 className="text-text-primary text-xl font-semibold mb-4 flex items-center gap-2">
                <Loader2 className="w-5 h-5 text-accent-primary animate-spin" />
                Post-Processing
              </h2>
              <div className="glass-card rounded-xl overflow-hidden">
                {snapshot.active
                  .filter((item) => item.status === 'processing')
                  .map((item) => (
                    <div key={item.id} className="flex items-center gap-4 p-4 border-b border-border last:border-b-0">
                      <div className="w-10 h-10 bg-bg-tertiary rounded-lg overflow-hidden flex-shrink-0">
                        {item.thumbnail_url ? (
                          <img src={item.thumbnail_url} alt={item.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <Loader2 className="w-5 h-5 text-accent-primary animate-spin" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-text-primary font-medium truncate">{item.title}</p>
                        <p className="text-text-secondary text-sm capitalize">{item.platform}</p>
                      </div>
                      <div className="flex items-center gap-2 text-accent-primary">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-sm font-medium">Post-processing...</span>
                      </div>
                    </div>
                  ))}
              </div>
            </section>
          )}

          {snapshot && snapshot.completed.length > 0 && (
            <section>
              <button
                onClick={() => setFailedOpen(!failedOpen)}
                className="flex items-center gap-2 text-text-primary text-xl font-semibold mb-4"
              >
                <AlertCircle className="w-5 h-5 text-status-error" />
                Failed / Completed ({snapshot.completed.length})
                <span className="text-text-muted text-sm">{failedOpen ? '▼' : '▶'}</span>
              </button>
              {failedOpen && (
                <div className="glass-card rounded-xl overflow-hidden">
                  {snapshot.completed.map((item) => (
                    <div key={item.id} className="flex items-center gap-4 p-4 border-b border-border last:border-b-0">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-text-primary font-medium">{item.title}</p>
                          {item.processed && (
                            <span className="px-2 py-0.5 rounded text-xs bg-accent-primary/20 text-accent-primary">Metadata</span>
                          )}
                        </div>
                        <p className="text-text-secondary text-sm capitalize">{item.platform}</p>
                      </div>
                      {item.processing_error && (
                        <div className="group relative">
                          <TriangleAlert className="w-4 h-4 text-status-warning" />
                          <div className="absolute bottom-full right-0 mb-2 px-3 py-2 bg-bg-elevated rounded-lg text-xs text-text-primary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                            Processing warning: {item.processing_error}. File is still usable.
                          </div>
                        </div>
                      )}
                      <button
                        onClick={() => retry(item.id)}
                        className="p-2 rounded-lg bg-accent-primary/20 text-accent-primary hover:bg-accent-primary hover:text-white transition-colors"
                        title="Retry"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {!snapshot || (snapshot.active.length === 0 && snapshot.queued.length === 0 && snapshot.paused.length === 0 && snapshot.completed.length === 0) ? (
            <div className="text-center py-20">
              <Activity className="w-16 h-16 text-text-muted mx-auto mb-4" />
              <h3 className="text-text-primary text-xl font-semibold mb-2">Queue is empty</h3>
              <p className="text-text-secondary">No downloads in progress. Start downloading to see them here.</p>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function ActiveDownloadCard({
  item,
  onPause,
  onResume,
  onCancel,
}: {
  item: { id: string; title: string; platform: string; thumbnail_url: string | null; progress: number; speed: number | null; eta: number | null; status: string };
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onCancel: (id: string) => void;
}) {
  const platformColor = PLATFORM_COLORS[item.platform] || 'bg-bg-tertiary';

  return (
    <motion.div layout className="glass-card rounded-xl p-4">
      <div className="flex items-center gap-4">
        <div className="w-24 h-16 bg-bg-tertiary rounded-lg overflow-hidden flex-shrink-0">
          {item.thumbnail_url ? (
            <img src={item.thumbnail_url} alt={item.title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Play className="w-6 h-6 text-text-muted" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-text-primary font-medium truncate">{item.title}</h3>
            <span className={`px-2 py-0.5 rounded text-xs text-white ${platformColor}`}>{item.platform}</span>
          </div>
          <div className="flex items-center gap-4 text-sm text-text-secondary mb-2">
            <span>{formatSpeed(item.speed)}</span>
            <span>ETA: {formatEta(item.eta)}</span>
            <span>{item.progress.toFixed(1)}%</span>
          </div>
          <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary"
              initial={{ width: 0 }}
              animate={{ width: `${item.progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => (item.status === 'paused' ? onResume(item.id) : onPause(item.id))}
            className={`p-2 rounded-lg transition-colors ${
              item.status === 'paused'
                ? 'bg-status-success/20 text-status-success hover:bg-status-success hover:text-white'
                : 'bg-status-paused/20 text-status-paused hover:bg-status-paused hover:text-white'
            }`}
            title={item.status === 'paused' ? 'Resume' : 'Pause'}
          >
            {item.status === 'paused' ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </button>
          <button
            onClick={() => onCancel(item.id)}
            className="p-2 rounded-lg bg-status-error/20 text-status-error hover:bg-status-error hover:text-white transition-colors"
            title="Cancel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function QueuedItem({
  item,
  index,
  onPrioritize,
  onCancel,
}: {
  item: { id: string; title: string; platform: string; thumbnail_url: string | null; position: number | null };
  index: number;
  onPrioritize: (id: string) => void;
  onCancel: (id: string) => void;
}) {
  const platformColor = PLATFORM_COLORS[item.platform] || 'bg-bg-tertiary';

  return (
    <motion.div layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4 p-4 border-b border-border last:border-b-0 hover:bg-bg-tertiary/50 transition-colors">
      <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary font-mono text-sm flex-shrink-0">
        {item.position ?? index + 1}
      </div>
      <div className="w-10 h-10 bg-bg-tertiary rounded-lg overflow-hidden flex-shrink-0">
        {item.thumbnail_url ? (
          <img src={item.thumbnail_url} alt={item.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Play className="w-4 h-4 text-text-muted" />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-text-primary font-medium truncate">{item.title}</p>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${platformColor}`} />
          <span className="text-text-secondary text-sm capitalize">{item.platform}</span>
        </div>
      </div>
      <button
        onClick={() => onPrioritize(item.id)}
        className="p-2 rounded-lg bg-status-warning/20 text-status-warning hover:bg-status-warning hover:text-white transition-colors"
        title="Prioritize"
      >
        <Star className="w-4 h-4" />
      </button>
      <button
        onClick={() => onCancel(item.id)}
        className="p-2 rounded-lg bg-status-error/20 text-status-error hover:bg-status-error hover:text-white transition-colors"
        title="Cancel"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </motion.div>
  );
}
