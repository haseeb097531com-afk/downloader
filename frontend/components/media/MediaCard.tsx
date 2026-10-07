'use client';

import { LibraryItem } from '@/lib/api/library';
import { Play, FolderOpen, Pencil, Trash2, Shield, Scissors, Cloud, CloudUpload, ExternalLink, Sparkles, FolderPlus } from 'lucide-react';
import { useState } from 'react';

interface MediaCardProps {
  item: LibraryItem;
  onPreview: (item: LibraryItem) => void;
  onOpenFolder: (id: string) => void;
  onRename: (item: LibraryItem) => void;
  onDelete: (item: LibraryItem) => void;
  onTrim?: (item: LibraryItem) => void;
  onBackup?: (id: string) => void;
  isBackingUp?: boolean;
  onAnalysis?: (item: LibraryItem) => void;
  onAddToCollection?: (item: LibraryItem) => void;
}

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'bg-platform-youtube',
  tiktok: 'bg-platform-tiktok',
  instagram: 'bg-platform-instagram',
  facebook: 'bg-platform-facebook',
  twitter: 'bg-platform-twitter',
  whatsapp: 'bg-platform-whatsapp',
};

export function MediaCard({ item, onPreview, onOpenFolder, onRename, onDelete, onTrim, onBackup, isBackingUp, onAnalysis, onAddToCollection }: MediaCardProps) {
  const [isHovered, setIsHovered] = useState(false);

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString();
  };

  const platformColor = PLATFORM_COLORS[item.platform] || 'bg-bg-tertiary';

  const hasTrim = item.trim_start && item.trim_end;

  return (
    <div
      className="glass-card rounded-xl overflow-hidden group cursor-pointer transition-all duration-300 hover:scale-[1.02]"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative aspect-video bg-bg-tertiary overflow-hidden">
        {(item.thumbnail_local || item.thumbnail_url) ? (
          <img
            src={item.thumbnail_local || item.thumbnail_url || ''}
            alt={item.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-accent-primary/20 to-accent-secondary/20">
            <Play className="w-12 h-12 text-text-muted" />
          </div>
        )}
        <div className="absolute top-2 left-2 flex gap-2">
          {item.category && (
            <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-bg-elevated/80 text-text-primary backdrop-blur-sm">
              {item.category}
            </span>
          )}
          <span className={`px-2 py-0.5 rounded-md text-xs font-medium text-white ${platformColor}`}>
            {item.platform}
          </span>
          {item.duration && (
            <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-black/60 text-white">
              {Math.floor(item.duration / 60)}:{(item.duration % 60).toString().padStart(2, '0')}
            </span>
          )}
          {item.processed && (
            <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-accent-primary/80 text-white">Metadata</span>
          )}
        </div>
        <div className="absolute top-2 right-2 flex gap-2">
          {hasTrim && (
            <span
              className="px-2 py-0.5 rounded-md text-xs font-medium bg-bg-elevated/80 text-text-primary backdrop-blur-sm flex items-center gap-1"
              title={`Trimmed: ${item.trim_start} - ${item.trim_end}`}
            >
              <Scissors className="w-3 h-3" />
            </span>
          )}
          {item.analysis_status === 'completed' && (
            <span
              className="px-2 py-0.5 rounded-md text-xs font-medium bg-accent-secondary/80 text-white flex items-center gap-1"
              title="AI Analysis complete"
            >
              <Sparkles className="w-3 h-3" />
            </span>
          )}
          {item.analysis_status === 'processing' && (
            <span
              className="px-2 py-0.5 rounded-md text-xs font-medium bg-accent-secondary/80 text-white flex items-center gap-1 animate-pulse"
              title="AI Analysis processing"
            >
              <Sparkles className="w-3 h-3" />
            </span>
          )}
          {item.cloud_backed_up && item.cloud_url && (
            <a
              href={item.cloud_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2 py-0.5 rounded-md text-xs font-medium bg-status-success/80 text-white flex items-center gap-1 hover:bg-status-success transition-colors"
              title="View in cloud"
            >
              <Cloud className="w-3 h-3" />
              <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </a>
          )}
          {item.is_watermark_free && (
            <div>
              <Shield className="w-5 h-5 text-status-success" />
            </div>
          )}
        </div>
        <div
          className={`absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center gap-3 transition-opacity duration-300 ${
            isHovered ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <button
            onClick={() => onPreview(item)}
            className="p-3 rounded-full bg-accent-primary hover:bg-accent-primary-hover text-white transition-colors"
            title="Preview"
          >
            <Play className="w-5 h-5" />
          </button>
          <button
            onClick={() => onOpenFolder(item.id)}
            className="p-3 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
            title="Open Folder"
          >
            <FolderOpen className="w-5 h-5" />
          </button>
          {onAddToCollection && (
            <button
              onClick={() => onAddToCollection(item)}
              className="p-3 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
              title="Add to Collection"
            >
              <FolderPlus className="w-5 h-5" />
            </button>
          )}
          {onTrim && (
            <button
              onClick={() => onTrim(item)}
              className="p-3 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
              title="Trim"
            >
              <Scissors className="w-5 h-5" />
            </button>
          )}
          {onAnalysis && (
            <button
              onClick={() => onAnalysis(item)}
              className="p-3 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
              title="AI Analysis"
            >
              {item.analysis_status === 'processing' ? (
                <Sparkles className="w-5 h-5 text-accent-secondary animate-pulse" />
              ) : (
                <Sparkles className="w-5 h-5" />
              )}
            </button>
          )}
          {onBackup && !item.cloud_backed_up && (
            <button
              onClick={() => onBackup(item.id)}
              disabled={isBackingUp}
              className="p-3 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors disabled:opacity-50"
              title="Backup to Cloud"
            >
              {isBackingUp ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <CloudUpload className="w-5 h-5" />
              )}
            </button>
          )}
          <button
            onClick={() => onRename(item)}
            className="p-3 rounded-full bg-bg-elevated hover:bg-bg-tertiary text-white transition-colors"
            title="Rename"
          >
            <Pencil className="w-5 h-5" />
          </button>
          <button
            onClick={() => onDelete(item)}
            className="p-3 rounded-full bg-status-error/80 hover:bg-status-error text-white transition-colors"
            title="Delete"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>
      <div className="p-4">
        <h3 className="text-text-primary font-medium text-sm line-clamp-2 min-h-[2.5rem]">
          {item.title}
        </h3>
        <div className="flex items-center justify-between mt-2 text-xs text-text-secondary">
          <span>{formatSize(item.file_size)}</span>
          <span>{formatDate(item.completed_at || item.created_at)}</span>
        </div>
      </div>
    </div>
  );
}
