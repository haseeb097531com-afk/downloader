import { create } from 'zustand';
import {
  getCollections,
  getCollection,
  createCollection,
  updateCollection,
  deleteCollection,
  addItemsToCollection,
  removeItemFromCollection,
  reorderCollectionItems,
  downloadExportBlob,
  buildExportUrl,
  triggerBlobDownload,
  Collection,
  CollectionDetail,
  NewCollectionPayload,
} from '../api/collections';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface CollectionsState {
  collections: Collection[];
  currentCollection: CollectionDetail | null;
  isLoading: boolean;
  isDetailLoading: boolean;
  toasts: Toast[];

  fetchCollections: () => Promise<void>;
  fetchCollection: (id: string) => Promise<void>;
  createNewCollection: (payload: NewCollectionPayload) => Promise<Collection>;
  renameCollection: (id: string, payload: NewCollectionPayload) => Promise<void>;
  deleteCollectionById: (id: string) => Promise<void>;
  addItems: (collectionId: string, downloadIds: string[]) => Promise<void>;
  removeItem: (collectionId: string, itemId: string) => Promise<void>;
  reorderItems: (collectionId: string, itemIds: string[]) => Promise<void>;
  exportCollection: (collectionId: string, format: 'm3u' | 'json') => Promise<void>;
  addToast: (message: string, type: Toast['type']) => void;
  dismissToast: (id: string) => void;
}

const generateId = () => Math.random().toString(36).slice(2, 9);

export const useCollectionsStore = create<CollectionsState>((set, get) => ({
  collections: [],
  currentCollection: null,
  isLoading: false,
  isDetailLoading: false,
  toasts: [],

  fetchCollections: async () => {
    set({ isLoading: true });
    try {
      const data = await getCollections();
      set({ collections: data });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load collections', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isLoading: false });
    }
  },

  fetchCollection: async (id) => {
    set({ isDetailLoading: true });
    try {
      const data = await getCollection(id);
      set({ currentCollection: data });
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to load collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } finally {
      set({ isDetailLoading: false });
    }
  },

  createNewCollection: async (payload) => {
    try {
      const data = await createCollection(payload);
      set((state) => ({ collections: [...state.collections, data] }));
      const toast = { id: generateId(), message: 'Collection created', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      return data;
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to create collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  renameCollection: async (id, payload) => {
    try {
      const updated = await updateCollection(id, payload);
      set((state) => ({
        collections: state.collections.map((c) => (c.id === id ? updated : c)),
        currentCollection: state.currentCollection?.id === id ? { ...state.currentCollection, ...updated } : state.currentCollection,
      }));
      const toast = { id: generateId(), message: 'Collection renamed', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to rename collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  deleteCollectionById: async (id) => {
    try {
      await deleteCollection(id);
      set((state) => ({
        collections: state.collections.filter((c) => c.id !== id),
        currentCollection: state.currentCollection?.id === id ? null : state.currentCollection,
      }));
      const toast = { id: generateId(), message: 'Collection deleted', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to delete collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  addItems: async (collectionId, downloadIds) => {
    try {
      const data = await addItemsToCollection(collectionId, { download_ids: downloadIds });
      set((state) => ({
        currentCollection: state.currentCollection?.id === collectionId ? data : state.currentCollection,
        collections: state.collections.map((c) => (c.id === collectionId ? { ...c, item_count: data.item_count } : c)),
      }));
      const toast = { id: generateId(), message: `Added ${downloadIds.length} item(s) to collection`, type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to add items to collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  removeItem: async (collectionId, itemId) => {
    try {
      const data = await removeItemFromCollection(collectionId, itemId);
      set((state) => ({
        currentCollection: state.currentCollection?.id === collectionId ? data : state.currentCollection,
        collections: state.collections.map((c) => (c.id === collectionId ? { ...c, item_count: data.item_count } : c)),
      }));
      const toast = { id: generateId(), message: 'Item removed from collection', type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to remove item from collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  reorderItems: async (collectionId, itemIds) => {
    try {
      const data = await reorderCollectionItems(collectionId, { item_ids: itemIds });
      set((state) => ({
        currentCollection: state.currentCollection?.id === collectionId ? data : state.currentCollection,
      }));
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to reorder collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  exportCollection: async (collectionId, format) => {
    try {
      const url = buildExportUrl(collectionId, format);
      const blob = await downloadExportBlob(url);
      const collection = get().collections.find((c) => c.id === collectionId);
      const name = collection?.name?.replace(/[^a-z0-9-_]+/gi, '_') || 'collection';
      triggerBlobDownload(blob, `${name}.${format}`);
      const toast = { id: generateId(), message: `Exported as ${format.toUpperCase()}`, type: 'success' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
    } catch (e) {
      console.error(e);
      const toast = { id: generateId(), message: 'Failed to export collection', type: 'error' as const };
      set((state) => ({ toasts: [...state.toasts, toast] }));
      setTimeout(() => get().dismissToast(toast.id), 4000);
      throw e;
    }
  },

  addToast: (message, type) => {
    const toast = { id: generateId(), message, type };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    setTimeout(() => get().dismissToast(toast.id), 4000);
  },

  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));
