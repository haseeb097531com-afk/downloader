'use client';

import { motion } from 'framer-motion';
import { FolderOpen, Pencil, Trash2, FolderHeart, Download } from 'lucide-react';
import { Collection } from '@/lib/api/collections';
import { useState } from 'react';

interface CollectionCardProps {
  collection: Collection;
  onOpen: () => void;
  onRename: () => void;
  onDelete: () => void;
  onExportM3u: () => void;
  onExportJson: () => void;
}

export function CollectionCard({ collection, onOpen, onRename, onDelete, onExportM3u, onExportJson }: CollectionCardProps) {
  const [isHovered, setIsHovered] = useState(false);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="glass-card rounded-xl overflow-hidden group cursor-pointer transition-all"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative aspect-[16/10] bg-gradient-to-br from-accent-primary/30 to-accent-secondary/30 flex items-center justify-center">
        <FolderHeart className="w-12 h-12 text-white/80" />
        <div className="absolute top-2 right-2 flex gap-1">
          <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-black/60 text-white">
            {collection.item_count} item{collection.item_count !== 1 ? 's' : ''}
          </span>
        </div>
        <div
          className={`absolute inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center gap-2 transition-opacity duration-300 ${
            isHovered ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <button
            onClick={onOpen}
            className="p-2 rounded-full bg-accent-primary hover:bg-accent-primary-hover text-white transition-colors"
            title="Open"
          >
            <FolderOpen className="w-5 h-5" />
          </button>
          <button
            onClick={onRename}
            className="p-2 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
            title="Rename"
          >
            <Pencil className="w-5 h-5" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-full bg-status-error/80 hover:bg-status-error text-white transition-colors"
            title="Delete"
          >
            <Trash2 className="w-5 h-5" />
          </button>
          <button
            onClick={onExportM3u}
            className="p-2 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
            title="Export M3U"
          >
            <Download className="w-5 h-5" />
          </button>
          <button
            onClick={onExportJson}
            className="p-2 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
            title="Export JSON"
          >
            <span className="text-xs font-bold">JSON</span>
          </button>
        </div>
      </div>
      <div className="p-4">
        <h3 className="text-text-primary font-medium text-sm line-clamp-1 mb-1">
          {collection.name}
        </h3>
        <p className="text-text-secondary text-xs line-clamp-2 min-h-[2rem]">
          {collection.description || 'No description'}
        </p>
        <div className="flex items-center justify-between mt-2 text-xs text-text-muted">
          <span>{collection.item_count} item{collection.item_count !== 1 ? 's' : ''}</span>
          <span>{formatDate(collection.updated_at)}</span>
        </div>
      </div>
    </motion.div>
  );
}

