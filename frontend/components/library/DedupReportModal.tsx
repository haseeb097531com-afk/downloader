'use client';

import { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle2, CopyX, AlertTriangle, Loader2, CheckSquare, Square } from 'lucide-react';
import { useDedupStore } from '@/lib/store/dedup';

interface DedupReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCleanupComplete?: (deletedCount: number) => void;
}

function getSimilarityColor(similarity: number): string {
  if (similarity > 90) return 'bg-status-success/20 text-status-success';
  if (similarity >= 70) return 'bg-status-warning/20 text-status-warning';
  return 'bg-status-info/20 text-status-info';
}

export default function DedupReportModal({ isOpen, onClose, onCleanupComplete }: DedupReportModalProps) {
  const { report, scanning, selectedDeleteIds, cleanupLoading, toggleDeleteSelection, runCleanup, setSelectedDeleteIds } = useDedupStore();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selectAll, setSelectAll] = useState(false);

  const allDuplicateIds = useMemo(() => {
    if (!report) return [];
    return report.groups.flatMap((g) => g.duplicates.map((d) => d.id));
  }, [report]);

  useEffect(() => {
    if (isOpen && report) {
      setSelectAll(false);
      setSelectedDeleteIds(new Set());
    }
  }, [isOpen, report, setSelectedDeleteIds]);

  useEffect(() => {
    if (selectAll) {
      setSelectedDeleteIds(new Set(allDuplicateIds));
    } else {
      setSelectedDeleteIds(new Set());
    }
  }, [selectAll, allDuplicateIds, setSelectedDeleteIds]);

  const handleDeleteSelected = async () => {
    const ids = Array.from(selectedDeleteIds);
    if (ids.length === 0) return;
    const result = await runCleanup(ids);
    if (result && onCleanupComplete) {
      onCleanupComplete(result.deleted_count);
    }
    setConfirmOpen(false);
    onClose();
  };

  const totalGroups = report?.groups.length ?? 0;
  const totalDuplicates = allDuplicateIds.length;
  const selectedCount = selectedDeleteIds.size;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget && !cleanupLoading) onClose();
          }}
        >
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="w-full max-w-2xl bg-bg-secondary border border-border rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col"
          >
            <div className="p-6 border-b border-border flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-accent-primary/20">
                  <CopyX className="w-5 h-5 text-accent-primary" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-text-primary">Duplicate Report</h2>
                  <p className="text-text-secondary text-sm">
                    {scanning
                      ? 'Scanning library...'
                      : totalGroups === 0
                        ? 'No duplicates found'
                        : `${totalGroups} group${totalGroups !== 1 ? 's' : ''} found, ${totalDuplicates} duplicate${totalDuplicates !== 1 ? 's' : ''} total`}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                disabled={cleanupLoading}
                className="p-1.5 rounded-lg text-text-muted hover:text-text-primary disabled:opacity-50 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {totalGroups === 0 && !scanning ? (
              <div className="flex-1 flex flex-col items-center justify-center py-16 px-6">
                <CheckCircle2 className="w-16 h-16 text-status-success mb-4" />
                <h3 className="text-text-primary text-xl font-semibold mb-2">No duplicates found</h3>
                <p className="text-text-secondary text-center text-sm">
                  Your library is clean! No duplicate files were detected.
                </p>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto p-6">
                  {scanning ? (
                    <div className="flex flex-col items-center justify-center py-16">
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
                        className="w-12 h-12 rounded-full border-2 border-accent-primary border-t-transparent mb-4"
                      />
                      <p className="text-text-secondary text-sm">Scanning library for duplicates...</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {totalGroups > 0 && (
                        <label className="flex items-center gap-2 mb-4 cursor-pointer select-none">
                          <button
                            type="button"
                            onClick={() => setSelectAll(!selectAll)}
                            className="text-text-secondary hover:text-text-primary transition-colors"
                          >
                            {selectAll ? <CheckSquare className="w-5 h-5 text-accent-primary" /> : <Square className="w-5 h-5" />}
                          </button>
                          <span className="text-sm text-text-secondary">Select All Duplicates</span>
                        </label>
                      )}

                      {report?.groups.map((group, groupIndex) => (
                        <motion.div
                          key={group.keep.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: groupIndex * 0.05 }}
                          className="rounded-xl border border-border overflow-hidden"
                        >
                          <div className="p-4 bg-status-success/5 border-b border-status-success/20">
                            <div className="flex items-center gap-2 mb-2">
                              <CheckCircle2 className="w-4 h-4 text-status-success shrink-0" />
                              <span className="text-xs font-medium text-status-success uppercase tracking-wide">Keep</span>
                            </div>
                            <div className="flex items-center gap-3">
                              {group.keep.thumbnail_url ? (
                                <img
                                  src={group.keep.thumbnail_url}
                                  alt=""
                                  className="w-20 h-14 object-cover rounded-lg shrink-0"
                                />
                              ) : (
                                <div className="w-20 h-14 rounded-lg bg-bg-tertiary flex items-center justify-center shrink-0">
                                  <CheckCircle2 className="w-5 h-5 text-text-muted" />
                                </div>
                              )}
                              <div className="flex-1 min-w-0">
                                <p className="text-text-primary text-sm font-medium truncate">{group.keep.title}</p>
                                <div className="flex items-center gap-2 mt-1">
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-bg-elevated text-text-secondary capitalize">
                                    {group.keep.platform}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="p-4 space-y-3">
                            {group.duplicates.map((dup) => {
                              const isSelected = selectedDeleteIds.has(dup.id);
                              return (
                                <div
                                  key={dup.id}
                                  onClick={() => toggleDeleteSelection(dup.id)}
                                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all border ${
                                    isSelected
                                      ? 'bg-status-error/10 border-status-error/30'
                                      : 'bg-bg-tertiary/30 border-transparent hover:bg-bg-tertiary/60'
                                  }`}
                                >
                                  <div className="shrink-0">
                                    {isSelected ? (
                                      <CheckSquare className="w-5 h-5 text-status-error" />
                                    ) : (
                                      <Square className="w-5 h-5 text-text-muted" />
                                    )}
                                  </div>
                                  {dup.thumbnail_url ? (
                                    <img
                                      src={dup.thumbnail_url}
                                      alt=""
                                      className="w-16 h-12 object-cover rounded-lg shrink-0"
                                    />
                                  ) : (
                                    <div className="w-16 h-12 rounded-lg bg-bg-tertiary flex items-center justify-center shrink-0">
                                      <CopyX className="w-4 h-4 text-text-muted" />
                                    </div>
                                  )}
                                  <div className="flex-1 min-w-0">
                                    <p className="text-text-primary text-sm font-medium truncate">{dup.title}</p>
                                    <div className="flex items-center gap-2 mt-1">
                                      <span className="text-xs px-2 py-0.5 rounded-full bg-bg-elevated text-text-secondary capitalize">
                                        {dup.platform}
                                      </span>
                                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getSimilarityColor(dup.similarity)}`}>
                                        {dup.similarity}% match
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="p-6 border-t border-border shrink-0">
                  {confirmOpen ? (
                    <div className="p-4 rounded-xl bg-status-error/10 border border-status-error/30 mb-4">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 text-status-error shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-text-primary text-sm font-medium">Permanently delete {selectedCount} file(s)?</p>
                          <p className="text-text-secondary text-xs mt-1">This action cannot be undone.</p>
                        </div>
                      </div>
                      <div className="flex gap-2 mt-4">
                        <button
                          onClick={() => setConfirmOpen(false)}
                          disabled={cleanupLoading}
                          className="flex-1 px-4 py-2.5 rounded-xl bg-bg-tertiary text-text-secondary text-sm font-medium hover:text-text-primary disabled:opacity-50 transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleDeleteSelected}
                          disabled={cleanupLoading}
                          className="flex-1 px-4 py-2.5 rounded-xl bg-status-error text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-2"
                        >
                          {cleanupLoading ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Deleting...
                            </>
                          ) : (
                            `Delete ${selectedCount}`
                          )}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmOpen(true)}
                      disabled={selectedCount === 0 || cleanupLoading}
                      className="w-full px-4 py-3 rounded-xl bg-status-error text-white font-medium hover:opacity-90 disabled:opacity-40 transition-opacity flex items-center justify-center gap-2"
                    >
                      <CopyX className="w-4 h-4" />
                      Delete Selected ({selectedCount})
                    </button>
                  )}
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

