'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TriangleAlert, Replace, X, CheckCircle2 } from 'lucide-react';
import { DuplicateMatch } from '@/lib/api/dedup';
import { dedupCleanup } from '@/lib/api/dedup';
import { createDownload } from '@/lib/api/downloads';
import { useDedupStore } from '@/lib/store/dedup';

interface DuplicateModalProps {
  isOpen: boolean;
  matches: DuplicateMatch[] | null;
  url: string;
  onClose: () => void;
}

function getSimilarityColor(similarity: number): string {
  if (similarity > 90) return 'bg-status-success/20 text-status-success';
  if (similarity >= 70) return 'bg-status-warning/20 text-status-warning';
  return 'bg-status-info/20 text-status-info';
}

function getSimilarityLabel(similarity: number): string {
  if (similarity > 90) return 'Very High';
  if (similarity >= 70) return 'High';
  return 'Medium';
}

export default function DuplicateModal({ isOpen, matches, url, onClose }: DuplicateModalProps) {
  const { addToast } = useDedupStore();
  const [replacing, setReplacing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [replaceConfirmed, setReplaceConfirmed] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !replacing) {
        addToast('Download skipped', 'info');
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, replacing, addToast, onClose]);

  useEffect(() => {
    if (!isOpen) {
      setReplacing(false);
      setDownloading(false);
      setReplaceConfirmed(false);
    }
  }, [isOpen]);

  const handleSkip = () => {
    addToast('Download skipped', 'info');
    onClose();
  };

  const handleDownloadAnyway = async () => {
    setDownloading(true);
    try {
      await createDownload({ url }, true);
      addToast('Download started (bypassed duplicate check)', 'success');
      onClose();
    } catch (e) {
      console.error(e);
      addToast('Failed to start download', 'error');
    } finally {
      setDownloading(false);
    }
  };

  const handleReplace = async () => {
    if (!replaceConfirmed) {
      setReplaceConfirmed(true);
      return;
    }
    if (!matches) return;
    setReplacing(true);
    try {
      const deleteIds = matches.map((m) => m.download_id);
      await dedupCleanup(deleteIds);
      await createDownload({ url }, true);
      addToast('Replaced and re-downloaded', 'success');
      onClose();
    } catch (e) {
      console.error(e);
      addToast('Failed to replace duplicate', 'error');
    } finally {
      setReplacing(false);
    }
  };

  const handleReplaceCancel = () => {
    setReplaceConfirmed(false);
  };

  return (
    <AnimatePresence>
      {isOpen && matches && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget && !replacing) handleSkip();
          }}
        >
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="w-full sm:max-w-lg bg-bg-secondary border border-status-warning/50 rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden"
            style={{ boxShadow: '0 0 30px rgba(253, 203, 110, 0.15)' }}
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-status-warning/20">
                    <TriangleAlert className="w-6 h-6 text-status-warning" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-text-primary">Possible Duplicate Detected</h2>
                    <p className="text-text-secondary text-sm mt-0.5">This video already exists in your library.</p>
                  </div>
                </div>
                <button
                  onClick={handleSkip}
                  disabled={replacing}
                  className="p-1 rounded-lg text-text-muted hover:text-text-primary disabled:opacity-50 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1 mb-6">
                {matches.map((match) => (
                  <div
                    key={match.download_id}
                    className="flex items-center gap-3 p-3 rounded-xl bg-bg-tertiary/50 border border-border"
                  >
                    {match.thumbnail_url ? (
                      <img
                        src={match.thumbnail_url}
                        alt=""
                        className="w-16 h-12 object-cover rounded-lg shrink-0"
                      />
                    ) : (
                      <div className="w-16 h-12 rounded-lg bg-bg-tertiary flex items-center justify-center shrink-0">
                        <CheckCircle2 className="w-5 h-5 text-text-muted" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary text-sm font-medium truncate">{match.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-bg-elevated text-text-secondary capitalize">
                          {match.platform}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getSimilarityColor(match.similarity)}`}>
                          {match.similarity}% {getSimilarityLabel(match.similarity)} match
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {replaceConfirmed && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="mb-4 p-4 rounded-xl bg-status-error/10 border border-status-error/30"
                >
                  <p className="text-text-primary text-sm font-medium mb-2">Confirm Replacement</p>
                  <p className="text-text-secondary text-xs mb-3">
                    This will permanently delete {matches.length} existing file(s) and re-download the new one.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={handleReplaceCancel}
                      disabled={replacing}
                      className="flex-1 px-3 py-2 rounded-lg bg-bg-tertiary text-text-secondary text-sm hover:text-text-primary disabled:opacity-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleReplace}
                      disabled={replacing}
                      className="flex-1 px-3 py-2 rounded-lg bg-status-error text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-1"
                    >
                      {replacing ? (
                        <>
                          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                            <Replace className="w-4 h-4" />
                          </motion.div>
                          Processing...
                        </>
                      ) : (
                        'Confirm Replace'
                      )}
                    </button>
                  </div>
                </motion.div>
              )}

              <div className="flex flex-col sm:flex-row gap-2">
                <button
                  onClick={handleSkip}
                  disabled={downloading || replacing}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-bg-tertiary text-text-secondary hover:text-text-primary text-sm font-medium transition-colors disabled:opacity-50"
                >
                  Skip
                </button>
                <button
                  onClick={handleDownloadAnyway}
                  disabled={downloading || replacing}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {downloading ? 'Starting...' : 'Download Anyway'}
                </button>
                <button
                  onClick={handleReplace}
                  disabled={downloading || replacing}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-status-error to-status-warning text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-1.5"
                >
                  <Replace className="w-4 h-4" />
                  {replaceConfirmed ? 'Confirm' : 'Replace Existing'}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
