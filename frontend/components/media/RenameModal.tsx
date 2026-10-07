'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface RenameModalProps {
  item: { id: string; title: string } | null;
  isOpen: boolean;
  onClose: () => void;
  onRename: (id: string, newName: string) => Promise<void>;
}

export function RenameModal({ item, isOpen, onClose, onRename }: RenameModalProps) {
  const [newName, setNewName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && item) {
      setNewName(item.title);
      setError('');
    }
  }, [isOpen, item]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!item || !newName.trim()) return;
    setError('');
    setIsSubmitting(true);
    try {
      await onRename(item.id, newName.trim());
      onClose();
    } catch {
      setError('Failed to rename file');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && item && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="glass-card rounded-xl p-6 w-full max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-text-primary text-lg font-semibold mb-4">Rename File</h2>
            <form onSubmit={handleSubmit}>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full px-4 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent-primary transition-colors"
                placeholder="Enter new filename"
                autoFocus
              />
              {error && <p className="text-status-error text-sm mt-2">{error}</p>}
              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !newName.trim()}
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium disabled:opacity-50 transition-opacity"
                >
                  {isSubmitting ? 'Renaming...' : 'Rename'}
                </button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

