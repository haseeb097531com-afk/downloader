'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, FolderPlus, FolderHeart, Plus } from 'lucide-react';
import { useCollectionsStore } from '@/lib/store/collections';

interface AddToCollectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  downloadIds: string[];
  onSuccess?: () => void;
}

export function AddToCollectionModal({ isOpen, onClose, downloadIds, onSuccess }: AddToCollectionModalProps) {
  const { collections, fetchCollections, addItems, createNewCollection } = useCollectionsStore();
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [addedTo, setAddedTo] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchCollections();
      setNewName('');
      setAddedTo(null);
    }
  }, [isOpen, fetchCollections]);

  const handleAdd = async (collectionId: string) => {
    if (addedTo) return;
    try {
      await addItems(collectionId, downloadIds);
      setAddedTo(collectionId);
      onSuccess?.();
    } catch {
      // handled by store toast
    }
  };

  const handleCreate = async () => {
    if (!newName.trim() || isCreating) return;
    setIsCreating(true);
    try {
      const collection = await createNewCollection({ name: newName.trim() });
      await addItems(collection.id, downloadIds);
      setAddedTo(collection.id);
      setNewName('');
      onSuccess?.();
    } catch {
      // handled by store toast
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
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
            className="glass-card rounded-xl p-6 w-full max-w-md mx-4 max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FolderPlus className="w-5 h-5 text-accent-primary" />
                <h2 className="text-text-primary text-lg font-semibold">Add to Collection</h2>
              </div>
              <button onClick={onClose} className="text-text-muted hover:text-text-primary">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mb-4">
              <p className="text-text-secondary text-sm mb-2">
                Add {downloadIds.length} item{downloadIds.length !== 1 ? 's' : ''} to:
              </p>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 mb-4">
              {collections.length === 0 && !isCreating ? (
                <p className="text-text-muted text-sm text-center py-4">No collections yet</p>
              ) : (
                collections.map((col) => (
                  <button
                    key={col.id}
                    onClick={() => handleAdd(col.id)}
                    disabled={!!addedTo}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-left ${
                      addedTo === col.id
                        ? 'bg-status-success/20 text-status-success border border-status-success/30'
                        : 'bg-bg-tertiary hover:bg-bg-elevated text-text-primary border border-transparent hover:border-border'
                    }`}
                  >
                    <FolderHeart className="w-5 h-5 text-accent-primary" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{col.name}</p>
                      <p className="text-xs text-text-muted">{col.item_count} item{col.item_count !== 1 ? 's' : ''}</p>
                    </div>
                    {addedTo === col.id && <span className="text-xs text-status-success">Added</span>}
                  </button>
                ))
              )}
            </div>

            <div className="border-t border-border pt-4">
              {isCreating ? (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="flex-1 px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary"
                    placeholder="Collection name"
                    autoFocus
                  />
                  <button
                    onClick={handleCreate}
                    disabled={!newName.trim()}
                    className="px-3 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium disabled:opacity-50"
                  >
                    Create & Add
                  </button>
                  <button
                    onClick={() => { setIsCreating(false); setNewName(''); }}
                    className="px-3 py-2 rounded-lg bg-bg-tertiary text-text-secondary text-sm hover:text-text-primary"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setIsCreating(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-dashed border-border text-text-secondary hover:text-text-primary hover:border-accent-primary/50 transition-all text-sm"
                >
                  <Plus className="w-4 h-4" />
                  New Collection
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
