'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { arrayMove } from '@dnd-kit/sortable';
import { restrictToVerticalAxis } from '@dnd-kit/modifiers';
import { useCollectionsStore } from '@/lib/store/collections';
import { MediaCard } from '@/components/media/MediaCard';
import { LibraryItem } from '@/lib/api/library';
import { AddToCollectionModal } from '@/components/collections/AddToCollectionModal';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  Download,
  FileJson,
  Film,
  GripVertical,
  Plus,
  X,
} from 'lucide-react';

function SortableMediaCard({ item, onRemove }: { item: LibraryItem; onRemove: (id: string) => void }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });

  const style: React.CSSProperties = {
    transform: transform
      ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
      : undefined,
    transition,
    opacity: isDragging ? 0.8 : 1,
    zIndex: isDragging ? 50 : undefined,
    position: 'relative',
  };

  return (
    <div ref={setNodeRef} style={style} className="relative group">
      <div className="absolute -left-8 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing text-text-muted hover:text-text-primary z-10 hidden sm:flex">
        <button {...attributes} {...listeners} className="p-1">
          <GripVertical className="w-5 h-5" />
        </button>
      </div>
      <MediaCard
        item={item}
        onPreview={() => {}}
        onOpenFolder={() => {}}
        onRename={() => {}}
        onDelete={() => onRemove(item.id)}
        onAddToCollection={() => {}}
      />
    </div>
  );
}

export default function CollectionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const collectionId = params.id as string;

  const {
    currentCollection,
    isDetailLoading,
    fetchCollection,
    removeItem,
    reorderItems,
    exportCollection,
    toasts,
    dismissToast,
  } = useCollectionsStore();

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  useEffect(() => {
    fetchCollection(collectionId);
  }, [collectionId, fetchCollection]);

  const handleRemove = async (itemId: string) => {
    await removeItem(collectionId, itemId);
  };

  const handleReorder = useCallback(
    async (reorderedItems: LibraryItem[]) => {
      await reorderItems(collectionId, reorderedItems.map((i) => i.id));
    },
    [collectionId, reorderItems]
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || !currentCollection) return;
      if (active.id === over.id) return;

      const items = currentCollection.items || [];
      const oldIndex = items.findIndex((i) => i.id === active.id);
      const newIndex = items.findIndex((i) => i.id === over.id);
      if (oldIndex === -1 || newIndex === -1) return;

      const reordered = arrayMove(items, oldIndex, newIndex);
      handleReorder(reordered);
    },
    [currentCollection, handleReorder]
  );

  const handleExport = async (format: 'm3u' | 'json') => {
    await exportCollection(collectionId, format);
  };

  const handleAddSuccess = useCallback(() => {
    fetchCollection(collectionId);
  }, [collectionId, fetchCollection]);

  if (isDetailLoading || !currentCollection) {
    return (
      <div className="max-w-7xl mx-auto p-4 sm:p-8">
        <div className="mb-8">
          <div className="h-8 bg-bg-tertiary rounded w-1/3 mb-2 animate-pulse" />
          <div className="h-4 bg-bg-tertiary rounded w-1/2 animate-pulse" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="glass-card rounded-xl overflow-hidden animate-pulse">
              <div className="aspect-video bg-bg-tertiary" />
              <div className="p-4">
                <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-2" />
                <div className="h-3 bg-bg-tertiary rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const items = currentCollection.items || [];
  const itemIds = items.map((i) => i.id);

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-8">
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-4">
          <button
            onClick={() => router.push('/collections')}
            className="p-2 rounded-lg hover:bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-text-primary mb-1">{currentCollection.name}</h1>
                <p className="text-text-secondary text-sm">
                  {items.length} item{items.length !== 1 ? 's' : ''}
                  {currentCollection.description && ` • ${currentCollection.description}`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleExport('m3u')}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-tertiary border border-border text-text-secondary hover:text-text-primary text-sm transition-colors"
                >
                  <Download className="w-4 h-4" />
                  M3U
                </button>
                <button
                  onClick={() => handleExport('json')}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-tertiary border border-border text-text-secondary hover:text-text-primary text-sm transition-colors"
                >
                  <FileJson className="w-4 h-4" />
                  JSON
                </button>
              </div>
            </div>
          </div>
        </div>
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

      {items.length === 0 ? (
        <div className="text-center py-20">
          <Film className="w-16 h-16 text-text-muted mx-auto mb-4" />
          <h3 className="text-text-primary text-xl font-semibold mb-2">This collection is empty</h3>
          <p className="text-text-secondary mb-6">Add videos from your library to get started</p>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity"
          >
            <Plus className="w-5 h-5" />
            Add Videos
          </button>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
          modifiers={[restrictToVerticalAxis]}
        >
          <SortableContext items={itemIds} strategy={verticalListSortingStrategy}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {items.map((item) => (
                <SortableMediaCard
                  key={item.id}
                  item={item}
                  onRemove={handleRemove}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      <AddToCollectionModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        downloadIds={items.map((i) => i.id)}
        onSuccess={handleAddSuccess}
      />
    </div>
  );
}
