'use client';

import { useEffect, useState } from 'react';
import { useCollectionsStore } from '@/lib/store/collections';
import { CollectionCard } from '@/components/collections/CollectionCard';
import { NewCollectionModal } from '@/components/collections/NewCollectionModal';
import { DeleteConfirmDialog } from '@/components/media/DeleteConfirmDialog';
import { RenameModal } from '@/components/media/RenameModal';
import {
  FolderHeart,
  Plus,
  X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';

export default function CollectionsPage() {
  const router = useRouter();
  const {
    collections,
    isLoading,
    fetchCollections,
    createNewCollection,
    renameCollection,
    deleteCollectionById,
    exportCollection,
    toasts,
    dismissToast,
  } = useCollectionsStore();

  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<{ id: string; title: string; name: string; description: string | null } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  const handleRename = async (id: string, newName: string) => {
    await renameCollection(id, { name: newName, description: renameTarget?.description || null });
    fetchCollections();
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteCollectionById(deleteTarget);
    setIsDeleteDialogOpen(false);
    setDeleteTarget(null);
  };

  const handleExport = async (id: string, format: 'm3u' | 'json') => {
    await exportCollection(id, format);
  };

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-8">
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Collections</h1>
          <p className="text-text-secondary">Organize your media into playlists and playlists</p>
        </div>
        <button
          onClick={() => setIsNewModalOpen(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity"
        >
          <Plus className="w-5 h-5" />
          New Collection
        </button>
      </div>

      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: -20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: -20, x: '-50%' }}
            className={`fixed top-4 left-1/2 z-50 px-6 py-3 rounded-lg shadow-lg ${
              toast.type === 'success' ? 'bg-status-success' : toast.type === 'error' ? 'bg-status-error' : 'bg-status-info'
            } text-white`}
          >
            {toast.message}
            <button onClick={() => dismissToast(toast.id)} className="ml-3 hover:opacity-80">
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="glass-card rounded-xl overflow-hidden animate-pulse">
              <div className="aspect-[16/10] bg-bg-tertiary" />
              <div className="p-4">
                <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-2" />
                <div className="h-3 bg-bg-tertiary rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : collections.length === 0 ? (
        <div className="text-center py-20">
          <FolderHeart className="w-16 h-16 text-text-muted mx-auto mb-4" />
          <h3 className="text-text-primary text-xl font-semibold mb-2">No collections yet</h3>
          <p className="text-text-secondary mb-6">Create your first collection to organize your media</p>
          <button
            onClick={() => setIsNewModalOpen(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity"
          >
            <Plus className="w-5 h-5" />
            New Collection
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {collections.map((col) => (
            <CollectionCard
              key={col.id}
              collection={col}
              onOpen={() => router.push(`/collections/${col.id}`)}
              onRename={() => {
                setRenameTarget({ id: col.id, title: col.name, name: col.name, description: col.description });
                setIsRenameModalOpen(true);
              }}
              onDelete={() => {
                setDeleteTarget(col.id);
                setIsDeleteDialogOpen(true);
              }}
              onExportM3u={() => handleExport(col.id, 'm3u')}
              onExportJson={() => handleExport(col.id, 'json')}
            />
          ))}
        </div>
      )}

      <NewCollectionModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onCreate={async (name, description) => {
          await createNewCollection({ name, description });
          fetchCollections();
        }}
      />

      <RenameModal
        item={renameTarget ? { id: renameTarget.id, title: renameTarget.name } : null}
        isOpen={isRenameModalOpen}
        onClose={() => {
          setIsRenameModalOpen(false);
          setRenameTarget(null);
        }}
        onRename={handleRename}
      />

      <DeleteConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setDeleteTarget(null);
        }}
        onConfirm={handleDelete}
        title="Delete Collection"
        message={
          deleteTarget
            ? `Are you sure you want to delete "${collections.find((c) => c.id === deleteTarget)?.name || 'this collection'}"? This action cannot be undone.`
            : ''
        }
      />
    </div>
  );
}
