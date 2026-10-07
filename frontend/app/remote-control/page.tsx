'use client';

import { useEffect, useState, useCallback } from 'react';
import { Suspense } from 'react';
import { useDeviceStore } from '@/lib/store/device';
import { getRemoteSummary, getRemoteQueue, pauseRemoteQueue, resumeRemoteQueue, cancelRemoteItem, submitClipboardUrl, createDownloadRemote, getRecentDownloads, getMediaFormats } from '@/lib/api/remote';
import { RemoteSummary, RemoteQueueItem } from '@/lib/api/remote';
import { QUALITY_PRESETS } from '@/lib/constants/quality-presets';
import {
  Smartphone,
  WifiOff,
  RefreshCw,
  Play,
  Pause,
  Square,
  Send,
  User,
  Home,
  ListTodo,
  Link as LinkIcon,
  Unlink,
  Camera,
  X,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

type ScannerProps = {
  onResult?: (result: { getText: () => string } | null) => void;
  constraints?: MediaStreamConstraints;
};

const QRScanner = (props: ScannerProps) => {
  const { onResult, constraints } = props;
  if (typeof window !== 'undefined') {
    void onResult;
    void constraints;
  }
  return null;
};

type Tab = 'home' | 'queue' | 'send' | 'me';

export default function RemoteControlPage() {
  const { token, isPaired, permissions, pair, unpair, deviceId, name } = useDeviceStore();
  const paired = isPaired();
  const [tab, setTab] = useState<Tab>('home');
  const [summary, setSummary] = useState<RemoteSummary | null>(null);
  const [queue, setQueue] = useState<RemoteQueueItem[]>([]);
  const [recent, setRecent] = useState<RemoteQueueItem[]>([]);
  const [isOnline, setIsOnline] = useState(true);
  const [pairCode, setPairCode] = useState('');
  const [pairName, setPairName] = useState('');
  const [isPairing, setIsPairing] = useState(false);
  const [showScanner, setShowScanner] = useState(false);
  const [url, setUrl] = useState('');
  const [quality, setQuality] = useState('best');
  const [sending, setSending] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);

  const has = (p: string) => permissions.includes(p);

  const refresh = useCallback(async () => {
    if (!paired || !token) return;
    try {
      const [s, q, r] = await Promise.all([
        getRemoteSummary(),
        getRemoteQueue(),
        getRecentDownloads(),
      ]);
      setSummary(s);
      setQueue(q);
      setRecent(r);
    } catch {
      // silent
    }
  }, [isPaired, token]);

  useEffect(() => {
    if (!paired) return;
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [paired, refresh]);

  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    setIsOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  const startScan = async () => {
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      setStream(media);
      setShowScanner(true);
    } catch {
      setShowScanner(false);
    }
  };

  const stopScan = () => {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      setStream(null);
    }
    setShowScanner(false);
  };

  const handleScan = (result: string) => {
    setPairCode(result);
    stopScan();
  };

  const handlePair = async () => {
    if (!pairCode.trim()) return;
    setIsPairing(true);
    await pair(pairCode.trim(), pairName.trim() || 'Mobile');
    setPairCode('');
    setPairName('');
    setIsPairing(false);
    setTab('home');
  };

  const handleUnpair = async () => {
    await unpair();
    setTab('home');
  };

  const handleSendUrl = async () => {
    if (!url.trim()) return;
    setSending(true);
    try {
      await submitClipboardUrl(url.trim());
      setUrl('');
    } catch {
      // silent
    } finally {
      setSending(false);
    }
  };

  const handleDownloadNow = async () => {
    if (!url.trim()) return;
    setSending(true);
    try {
      await createDownloadRemote({ url: url.trim(), quality });
      setUrl('');
    } catch {
      // silent
    } finally {
      setSending(false);
    }
  };

  if (!paired) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <Smartphone className="w-12 h-12 text-accent-primary mx-auto mb-3" />
            <h1 className="text-2xl font-bold text-text-primary">Remote Control</h1>
            <p className="text-text-secondary text-sm mt-1">Pair with your desktop to continue</p>
          </div>
          <div className="glass-card rounded-2xl p-6 space-y-4">
            <div>
              <label className="block text-text-primary text-sm font-medium mb-2">Device name</label>
              <input
                type="text"
                value={pairName}
                onChange={(e) => setPairName(e.target.value)}
                placeholder="My Phone"
                className="w-full px-4 py-3 bg-bg-tertiary border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
              />
            </div>
            <div>
              <label className="block text-text-primary text-sm font-medium mb-2">Pairing code</label>
              <input
                type="text"
                value={pairCode}
                onChange={(e) => setPairCode(e.target.value)}
                placeholder="ABC123"
                className="w-full px-4 py-3 bg-bg-tertiary border border-border rounded-xl text-text-primary placeholder:text-text-muted text-center text-2xl font-mono tracking-widest focus:outline-none focus:border-accent-primary"
              />
            </div>
            <button
              onClick={startScan}
              className="w-full py-3 rounded-xl border border-border text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors inline-flex items-center justify-center gap-2"
            >
              <Camera className="w-5 h-5" />
              Scan QR code
            </button>
            <button
              onClick={handlePair}
              disabled={!pairCode.trim() || isPairing}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {isPairing ? 'Pairing...' : 'Pair'}
            </button>
          </div>
          {showScanner && (
            <div className="fixed inset-0 z-50 bg-black">
              <Suspense fallback={<div className="p-4 text-white">Loading camera...</div>}>
                <QRScanner
                  onResult={(result) => result && handleScan(result.getText())}
                  constraints={{ video: { facingMode: 'environment' } }}
                />
              </Suspense>
              <button
                onClick={stopScan}
                className="absolute top-4 right-4 p-2 rounded-full bg-white/20 text-white"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: LucideIcon }[] = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'queue', label: 'Queue', icon: ListTodo },
    { id: 'send', label: 'Send', icon: Send },
    { id: 'me', label: 'Me', icon: User },
  ];

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col max-w-md mx-auto relative">
      {!isOnline && (
        <div className="bg-status-warning text-white text-center py-2 text-sm flex items-center justify-center gap-2">
          <WifiOff className="w-4 h-4" /> Offline — some features unavailable
        </div>
      )}

      <main className="flex-1 overflow-y-auto pb-24 p-4">
        <AnimatePresence mode="wait">
          {tab === 'home' && (
            <motion.div key="home" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
                <button onClick={refresh} className="p-2 rounded-lg hover:bg-bg-tertiary text-text-secondary">
                  <RefreshCw className="w-5 h-5" />
                </button>
              </div>
              {summary && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="glass-card rounded-xl p-4">
                      <p className="text-text-muted text-xs mb-1">Disk free</p>
                      <p className="text-text-primary font-semibold text-lg">{summary.disk_free_gb.toFixed(1)} GB</p>
                    </div>
                    <div className="glass-card rounded-xl p-4">
                      <p className="text-text-muted text-xs mb-1">Speed</p>
                      <p className="text-text-primary font-semibold text-lg">{(summary.current_speed_mbps / 8).toFixed(1)} MB/s</p>
                    </div>
                    <div className="glass-card rounded-xl p-4">
                      <p className="text-text-muted text-xs mb-1">Workers</p>
                      <p className="text-text-primary font-semibold text-lg">{summary.active_workers}</p>
                    </div>
                    <div className="glass-card rounded-xl p-4">
                      <p className="text-text-muted text-xs mb-1">Queue</p>
                      <p className="text-text-primary font-semibold text-lg">{summary.queue_length}</p>
                    </div>
                  </div>
                  <div className="glass-card rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-text-secondary text-sm">Disk usage</span>
                      <span className="text-text-primary text-sm font-mono">
                        {((summary.disk_total_gb - summary.disk_free_gb) / summary.disk_total_gb * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="w-full h-3 bg-bg-tertiary rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary transition-all duration-500"
                        style={{ width: `${((summary.disk_total_gb - summary.disk_free_gb) / summary.disk_total_gb) * 100}%` }}
                      />
                    </div>
                  </div>
                </>
              )}
            </motion.div>
          )}

          {tab === 'queue' && (
            <motion.div key="queue" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-3">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-text-primary">Queue</h1>
                {has('control') && (
                  <div className="flex gap-2">
                    <button onClick={pauseRemoteQueue} className="px-3 py-2 rounded-lg bg-bg-tertiary text-text-secondary text-sm">
                      Pause all
                    </button>
                    <button onClick={resumeRemoteQueue} className="px-3 py-2 rounded-lg bg-bg-tertiary text-text-secondary text-sm">
                      Resume all
                    </button>
                  </div>
                )}
              </div>
              {queue.length === 0 && <p className="text-text-muted text-center py-8">Queue is empty</p>}
              {queue.map((item) => (
                <div key={item.id} className="glass-card rounded-xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-text-primary font-medium text-sm line-clamp-1">{item.title}</p>
                    <span className="text-text-muted text-xs capitalize">{item.status}</span>
                  </div>
                  <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
                    <div className="h-full bg-accent-primary rounded-full transition-all" style={{ width: `${item.progress}%` }} />
                  </div>
                  {has('control') && (
                    <div className="flex gap-2">
                      <button className="flex-1 py-2 rounded-lg bg-bg-tertiary text-text-secondary text-xs inline-flex items-center justify-center gap-1">
                        <Pause className="w-3 h-3" /> Pause
                      </button>
                      <button className="flex-1 py-2 rounded-lg bg-bg-tertiary text-text-secondary text-xs inline-flex items-center justify-center gap-1">
                        <Play className="w-3 h-3" /> Resume
                      </button>
                      <button
                        onClick={() => cancelRemoteItem(item.id)}
                        className="flex-1 py-2 rounded-lg bg-status-error/20 text-status-error text-xs inline-flex items-center justify-center gap-1"
                      >
                        <Square className="w-3 h-3" /> Cancel
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </motion.div>
          )}

          {tab === 'send' && (
            <motion.div key="send" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
              <h1 className="text-xl font-bold text-text-primary">Send</h1>
              <div className="glass-card rounded-xl p-4 space-y-3">
                <label className="block text-text-primary text-sm font-medium">URL</label>
                <textarea
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Paste link here..."
                  rows={3}
                  className="w-full px-4 py-3 bg-bg-tertiary border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleSendUrl}
                    disabled={sending || !url.trim()}
                    className="flex-1 py-3 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 inline-flex items-center justify-center gap-2"
                  >
                    <LinkIcon className="w-4 h-4" /> Send to desktop
                  </button>
                  <button
                    onClick={handleDownloadNow}
                    disabled={sending || !url.trim()}
                    className="flex-1 py-3 rounded-xl bg-bg-tertiary text-text-primary font-medium hover:bg-bg-elevated disabled:opacity-50 inline-flex items-center justify-center gap-2"
                  >
                    <Send className="w-4 h-4" /> Download now
                  </button>
                </div>
                <div>
                  <label className="block text-text-primary text-sm font-medium mb-2">Quality</label>
                  <select
                    value={quality}
                    onChange={(e) => setQuality(e.target.value)}
                    className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-xl text-text-primary focus:outline-none focus:border-accent-primary"
                  >
                    {QUALITY_PRESETS.map(q => (
                      <option key={q.value} value={q.value}>{q.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-text-secondary text-sm font-medium">Recent</p>
                {recent.map((item) => (
                  <div key={item.id} className="glass-card rounded-xl p-3 flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-text-primary text-sm line-clamp-1">{item.title}</p>
                      <p className="text-text-muted text-xs capitalize">{item.platform}</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-text-muted" />
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {tab === 'me' && (
            <motion.div key="me" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
              <h1 className="text-xl font-bold text-text-primary">Me</h1>
              <div className="glass-card rounded-xl p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-primary flex items-center justify-center text-white font-bold text-lg">
                    {(name || 'U')[0].toUpperCase()}
                  </div>
                  <div>
                    <p className="text-text-primary font-medium">{name || 'Unknown'}</p>
                    <p className="text-text-muted text-xs">ID: {deviceId?.slice(0, 8)}...</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {permissions.map((p) => (
                    <span key={p} className="px-3 py-1 rounded-full bg-accent-primary/20 text-accent-primary text-xs font-medium capitalize">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
              <button
                onClick={handleUnpair}
                className="w-full py-3 rounded-xl border border-status-error text-status-error hover:bg-status-error/10 transition-colors inline-flex items-center justify-center gap-2"
              >
                <Unlink className="w-4 h-4" /> Unpair device
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {paired ? (
        <nav className="fixed bottom-0 left-0 right-0 bg-bg-elevated/80 backdrop-blur-md border-t border-border flex justify-around items-center h-16 pb-safe">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex flex-col items-center justify-center gap-1 w-full h-full ${
                  active ? 'text-accent-primary' : 'text-text-muted'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-[10px] font-medium">{t.label}</span>
              </button>
            );
          })}
        </nav>
      ) : null}
    </div>
  );
}
