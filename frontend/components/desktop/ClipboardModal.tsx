'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, Loader2 } from 'lucide-react';
import { useDesktopStore } from '@/lib/store/desktop';

const COUNTDOWN_SECONDS = 15;

const PLATFORM_CONFIG: Record<
  string,
  { label: string; color: string; glowClass: string }
> = {
  youtube: { label: 'YouTube', color: '#FF0000', glowClass: 'glow-youtube' },
  tiktok: { label: 'TikTok', color: '#00F2EA', glowClass: 'glow-tiktok' },
  instagram: { label: 'Instagram', color: '#E4405F', glowClass: 'glow-instagram' },
  facebook: { label: 'Facebook', color: '#1877F2', glowClass: 'glow-facebook' },
  twitter: { label: 'Twitter', color: '#1DA1F2', glowClass: '' },
  whatsapp: { label: 'WhatsApp', color: '#25D366', glowClass: '' },
};

function timeAgo(dateStr: string) {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ClipboardModal() {
  const {
    activePending,
    modalOpen,
    isDownloading,
    downloadActive,
    dismissActive,
    toasts,
    dismissToast,
    fetchPending,
  } = useDesktopStore();

  const [hovered, setHovered] = useState(false);
  const [remaining, setRemaining] = useState(COUNTDOWN_SECONDS);

  const platform = activePending
    ? PLATFORM_CONFIG[activePending.platform.toLowerCase()] || {
        label: activePending.platform,
        color: '#888888',
        glowClass: '',
      }
    : null;

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  useEffect(() => {
    if (!modalOpen || !activePending) return;
    setRemaining(COUNTDOWN_SECONDS);
  }, [activePending, activePending?.id, modalOpen]);

  useEffect(() => {
    if (!modalOpen || hovered) return;
    const timer = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          dismissActive();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [modalOpen, hovered, dismissActive]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && modalOpen) {
        dismissActive();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [modalOpen, dismissActive]);

  return (
    <>
      <AnimatePresence>
        {modalOpen && activePending && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={(e) => {
              e.stopPropagation();
              dismissActive();
            }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              onMouseEnter={() => setHovered(true)}
              onMouseLeave={() => setHovered(false)}
              className={`glass-card rounded-xl p-6 w-full max-w-md mx-4 ${
                platform?.glowClass || ''
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-full h-1 bg-bg-tertiary rounded-full mb-6 overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-primary rounded-full"
                  initial={{ width: '100%' }}
                  animate={{
                    width: `${(remaining / COUNTDOWN_SECONDS) * 100}%`,
                  }}
                  transition={{ duration: 1, ease: 'linear' }}
                />
              </div>

              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-sm shrink-0"
                  style={{ backgroundColor: platform?.color || '#888888' }}
                >
                  {platform?.label.slice(0, 2).toUpperCase() || '??'}
                </div>
                <div className="flex-1 min-w-0">
                  <span
                    className="inline-block px-2.5 py-1 rounded-full text-xs font-medium text-white"
                    style={{ backgroundColor: platform?.color || '#888888' }}
                  >
                    {platform?.label || activePending.platform}
                  </span>
                  <p className="text-text-muted text-xs mt-1">
                    {timeAgo(activePending.detected_at)}
                  </p>
                </div>
              </div>

              <div className="mb-6 p-3 rounded-lg bg-bg-tertiary/50 border border-border">
                <p
                  className="font-mono text-sm text-text-primary truncate"
                  title={activePending.url}
                >
                  {activePending.url}
                </p>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  onClick={dismissActive}
                  className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors flex items-center gap-2"
                >
                  <X className="w-4 h-4" />
                  Ignore
                </button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={downloadActive}
                  disabled={isDownloading}
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
                >
                  {isDownloading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" />
                      Download Now
                    </>
                  )}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: -20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: -20, x: '-50%' }}
            className={`fixed top-4 left-1/2 z-50 px-6 py-3 rounded-lg shadow-lg ${
              toast.type === 'success'
                ? 'bg-status-success'
                : toast.type === 'error'
                  ? 'bg-status-error'
                  : 'bg-status-info'
            } text-white`}
          >
            {toast.message}
            <button
              onClick={() => dismissToast(toast.id)}
              className="ml-3 hover:opacity-80"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </>
  );
}

