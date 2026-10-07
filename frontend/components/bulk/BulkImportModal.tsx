'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ListPlus, Link, User, Send } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { bulkImportLinks, bulkImportProfiles, BulkJobResponse } from '@/lib/api/bulk';

interface BulkImportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Mode = 'links' | 'profiles';

export function BulkImportModal({ isOpen, onClose }: BulkImportModalProps) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('links');
  const [text, setText] = useState('');
  const [limit, setLimit] = useState(50);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validCount, setValidCount] = useState(0);
  const [invalidCount, setInvalidCount] = useState(0);

  useEffect(() => {
    if (!isOpen) {
      setText('');
      setMode('links');
      setLimit(50);
      setValidCount(0);
      setInvalidCount(0);
    }
  }, [isOpen]);

  useEffect(() => {
    const lines = text.split(/[\n\r]+/).map((l) => l.trim()).filter(Boolean);
    let valid = 0;
    let invalid = 0;
    for (const line of lines) {
      if (/^https?:\/\//i.test(line)) {
        valid++;
      } else if (mode === 'profiles' && line.includes('/')) {
        valid++;
      } else {
        invalid++;
      }
    }
    setValidCount(valid);
    setInvalidCount(invalid);
  }, [text, mode]);

  const handleSubmit = async () => {
    if (validCount === 0) return;
    setIsSubmitting(true);
    try {
      let result: BulkJobResponse;
      if (mode === 'links') {
        const links = text.split(/[\n\r]+/).map((l) => l.trim()).filter(Boolean);
        result = await bulkImportLinks({ links });
      } else {
        const profiles = text.split(/[\n\r]+/).map((l) => l.trim()).filter(Boolean);
        result = await bulkImportProfiles({ profiles, limit_per_profile: limit });
      }
      router.push(`/bulk/${result.job_id}`);
      onClose();
    } catch (e) {
      console.error(e);
      alert('Failed to start bulk import');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="glass-card w-full max-w-2xl rounded-2xl border border-white/10 overflow-hidden relative shadow-2xl"
          >
            <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-white transition">
              <X size={20} />
            </button>

            <div className="p-6">
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 rounded-xl bg-accent-primary/20 border border-accent-primary/30">
                  <ListPlus className="w-6 h-6 text-accent-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-text-primary">Bulk Import</h2>
                  <p className="text-sm text-text-secondary">Import multiple videos or profiles at once</p>
                </div>
              </div>

              <div className="flex items-center gap-2 p-1 bg-bg-tertiary rounded-lg mb-4">
                {([
                  { key: 'links', label: 'Video Links', icon: Link },
                  { key: 'profiles', label: 'Profiles / IDs', icon: User },
                ] as const).map((option) => (
                  <button
                    key={option.key}
                    onClick={() => setMode(option.key)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-all ${
                      mode === option.key
                        ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                        : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <option.icon className="w-4 h-4" />
                    {option.label}
                  </button>
                ))}
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  {mode === 'links' ? 'Paste video URLs' : 'Paste profile URLs or usernames'}
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={mode === 'links' ? 'Paste up to hundreds of links, one per line...' : 'Paste profile URLs or usernames, one per line...'}
                  className="w-full h-48 p-4 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted font-mono text-sm focus:outline-none focus:border-accent-primary transition-colors resize-none"
                />
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-text-muted">
                    Detected: <span className="text-status-success">{validCount} valid</span>
                    {invalidCount > 0 && <span className="text-status-error ml-2">{invalidCount} invalid</span>}
                  </span>
                  <span className="text-xs text-text-muted">{text.split(/[\n\r]+/).filter(Boolean).length} lines</span>
                </div>
              </div>

              {mode === 'profiles' && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-text-secondary mb-1.5">Limit per profile</label>
                  <div className="flex items-center gap-2">
                    {[10, 25, 50, 100].map((v) => (
                      <button
                        key={v}
                        onClick={() => setLimit(v)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                          limit === v
                            ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                            : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                    <button
                      onClick={() => setLimit(999)}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                        limit === 999
                          ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                          : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      All
                    </button>
                  </div>
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={isSubmitting || validCount === 0}
                className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium flex items-center justify-center gap-2 transition-all hover:opacity-90 disabled:opacity-50 shadow-[0_0_15px_rgba(108,92,231,0.4)]"
              >
                {isSubmitting ? (
                  <>
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }} className="w-4 h-4 rounded-full border-2 border-white border-t-transparent" />
                    Importing...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Import All
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

