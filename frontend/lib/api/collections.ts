import { LibraryItem } from './library';

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  item_count: number;
  updated_at: string;
}

export interface CollectionItem {
  id: string;
  collection_id: string;
  download_id: string;
  sort_order: number;
  created_at: string;
}

export interface CollectionDetail extends Collection {
  items: LibraryItem[];
}

export interface NewCollectionPayload {
  name: string;
  description?: string | null;
}

export interface RenameCollectionPayload {
  name: string;
  description?: string | null;
}

export interface AddItemsPayload {
  download_ids: string[];
}

export interface ReorderItemsPayload {
  item_ids: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function getCollections(): Promise<Collection[]> {
  const res = await fetch(`${API_BASE}/collections`);
  if (!res.ok) throw new Error('Failed to fetch collections');
  return res.json();
}

export async function getCollection(id: string): Promise<CollectionDetail> {
  const res = await fetch(`${API_BASE}/collections/${id}`);
  if (!res.ok) throw new Error('Failed to fetch collection');
  return res.json();
}

export async function createCollection(payload: NewCollectionPayload): Promise<Collection> {
  const res = await fetch(`${API_BASE}/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create collection');
  return res.json();
}

export async function updateCollection(id: string, payload: RenameCollectionPayload): Promise<Collection> {
  const res = await fetch(`${API_BASE}/collections/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update collection');
  return res.json();
}

export async function deleteCollection(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/collections/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete collection');
}

export async function addItemsToCollection(id: string, payload: AddItemsPayload): Promise<CollectionDetail> {
  const res = await fetch(`${API_BASE}/collections/${id}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to add items to collection');
  return res.json();
}

export async function removeItemFromCollection(collectionId: string, itemId: string): Promise<CollectionDetail> {
  const res = await fetch(`${API_BASE}/collections/${collectionId}/items/${itemId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to remove item from collection');
  return res.json();
}

export async function reorderCollectionItems(id: string, payload: ReorderItemsPayload): Promise<CollectionDetail> {
  const res = await fetch(`${API_BASE}/collections/${id}/items/reorder`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to reorder collection');
  return res.json();
}

export async function downloadExportBlob(url: string): Promise<Blob> {
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to download export');
  return res.blob();
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function buildExportUrl(collectionId: string, format: 'm3u' | 'json'): string {
  return `${API_BASE}/collections/${collectionId}/export/${format}`;
}

