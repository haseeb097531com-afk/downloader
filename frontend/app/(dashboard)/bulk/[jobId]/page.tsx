'use client';

import { useEffect, useState, useRef, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, RotateCcw, CheckCircle2, AlertCircle, Wifi, WifiOff } from 'lucide-react';
import { getBulkJob, retryBulkJob, BulkJobStatus } from '@/lib/api/bulk';

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'bg-platform-youtube',
  tiktok: 'bg-platform-tiktok',
  instagram: 'bg-platform-instagram',
  facebook: 'bg-platform-facebook',
  twitter: 'bg-platform-twitter',
  other: 'bg-bg-tertiary',
};

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-status-queued',
  downloading: 'bg-status-downloading',
  completed: 'bg-status-success',
  failed: 'bg-status-error',
};

export default function BulkProgressPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const router = useRouter();

  const [job, setJob] = useState<BulkJobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetrying, setIsRetrying] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchJob = async () => {
    try {
      const data = await getBulkJob(jobId);
      setJob(data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchJob();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || '/ws';
    const ws = new WebSocket(`${wsUrl}/bulk/${jobId}`);
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setJob(data);
      } catch {
        // ignore parse errors
      }
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await retryBulkJob(jobId);
      await fetchJob();
    } catch (e) {
      console.error(e);
      alert('Failed to retry failed items');
    } finally {
      setIsRetrying(false);
    }
  };

  const progress = useMemo(() => {
    if (!job || job.total === 0) return 0;
    return Math.round(((job.completed + job.failed) / job.total) * 100);
  }, [job]);

  const failedItems = useMemo(() => job?.items.filter((i) => i.status === 'failed') || [], [job]);
  const isComplete = job?.status === 'completed' || (job && job.completed + job.failed >= job.total);

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto p-8 flex items-center justify-center min-h-[50vh]">
        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }} className="w-8 h-8 rounded-full border-2 border-accent-primary border-t-transparent" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="max-w-5xl mx-auto p-8 text-center">
        <p className="text-text-secondary">Job not found</p>
        <button onClick={() => router.push('/')} className="mt-4 px-4 py-2 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary">
          Go Home
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => router.back()} className="p-2 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary transition">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-text-primary mb-1">Bulk Import Progress</h1>
            <div className="flex items-center gap-2 text-sm text-text-secondary">
              <span>Job: {job.job_id.slice(0, 8)}...</span>
              <span className={`flex items-center gap-1 ${wsConnected ? 'text-status-success' : 'text-status-error'}`}>
                {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {wsConnected ? 'Live' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {isComplete && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-status-success/10 border border-status-success/30 flex items-center gap-3"
        >
          <CheckCircle2 className="w-5 h-5 text-status-success" />
          <span className="text-status-success font-medium">All downloads processed!</span>
        </motion.div>
      )}

      <div className="glass-card rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <span className="text-text-primary font-medium">Overall Progress</span>
          <span className="text-text-secondary text-sm">
            {job.completed} / {job.total} completed
            {job.failed > 0 && <span className="text-status-error ml-2">{job.failed} failed</span>}
          </span>
        </div>
        <div className="w-full h-3 bg-bg-tertiary rounded-full overflow-hidden mb-2">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>{progress}%</span>
          <span>{job.total - job.completed - job.failed} remaining</span>
        </div>
      </div>

      <div className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="p-4 border-b border-border">
          <h3 className="text-text-primary font-semibold">Items</h3>
        </div>
        <div className="max-h-[400px] overflow-y-auto">
          {job.items.map((item) => (
            <div key={item.id} className="flex items-center gap-4 p-4 border-b border-border last:border-b-0 hover:bg-bg-tertiary/50 transition-colors">
              <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center">
                <div className={`w-2.5 h-2.5 rounded-full ${PLATFORM_COLORS[item.platform] || 'bg-bg-tertiary'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-text-primary text-sm font-medium truncate">{item.url}</p>
                <p className="text-text-muted text-xs capitalize">{item.platform}</p>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[item.status] || 'bg-bg-tertiary text-text-secondary'}`}>
                {item.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {failedItems.length > 0 && (
        <div className="glass-card rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-text-primary font-semibold flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-status-error" />
              Failed Items ({failedItems.length})
            </h3>
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="px-4 py-2 rounded-lg bg-status-error/20 text-status-error hover:bg-status-error hover:text-white disabled:opacity-50 transition-colors flex items-center gap-2 text-sm font-medium"
            >
              {isRetrying ? (
                <>
                  <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }} className="w-4 h-4 rounded-full border-2 border-status-error border-t-transparent" />
                  Retrying...
                </>
              ) : (
                <>
                  <RotateCcw className="w-4 h-4" />
                  Retry Failed
                </>
              )}
            </button>
          </div>
          <div className="space-y-3">
            {failedItems.map((item) => (
              <div key={item.id} className="p-4 rounded-lg bg-status-error/10 border border-status-error/20">
                <p className="text-text-primary text-sm font-medium truncate">{item.url}</p>
                {item.error && <p className="text-status-error text-xs mt-1">{item.error}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
