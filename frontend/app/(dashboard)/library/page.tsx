'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
import { LibraryItem, PlatformStat } from '@/lib/api/library';
import { useLibraryStore } from '@/lib/store/library';
import { useDedupStore } from '@/lib/store/dedup';
import { MediaCard } from '@/components/media/MediaCard';
import { MediaPreviewModal } from '@/components/media/MediaPreviewModal';
import { RenameModal } from '@/components/media/RenameModal';
import { DeleteConfirmDialog } from '@/components/media/DeleteConfirmDialog';
import { TrimmerModal } from '@/components/media/TrimmerModal';
import { AnalysisModal } from '@/components/media/AnalysisModal';
import DedupReportModal from '@/components/library/DedupReportModal';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { AddToCollectionModal } from '@/components/collections/AddToCollectionModal';
import { backupDownload } from '@/lib/api/cloud';
import {
  HardDrive,
  TrendingUp,
  Film,
  Download,
  X,
  Sparkles,
  Search,
  CopyX,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const PLATFORM_COLORS: Record<string, string> = {
  youtube: '#FF0000',
  tiktok: '#00F2EA',
  instagram: '#E4405F',
  facebook: '#1877F2',
  twitter: '#1DA1F2',
  whatsapp: '#25D366',
};

const CHART_COLORS = ['#6C5CE7', '#00D2FF', '#FF6B6B', '#00B894', '#FD79A8', '#A29BFE'];

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export default function LibraryPage() {
  const {
    items,
    stats,
    categories,
    untracked,
    page,
    totalPages,
    hasNext,
    platform,
    category,
    search,
    isLoading,
    isStatsLoading,
    fetchLibrary,
    fetchStats,
    fetchUntracked,
    fetchCategories,
    importUntracked,
    renameItem,
    deleteItem,
    openFolder,
    setPage,
    setCategory,
    setSearch,
    toasts,
    dismissToast,
    addToast,
  } = useLibraryStore();

  const { scanning, startScan, fetchReport, clearReport } = useDedupStore();

  const [searchInput, setSearchInput] = useState(search);
  const [selectedItem, setSelectedItem] = useState<LibraryItem | null>(null);
  const [renameTarget, setRenameTarget] = useState<LibraryItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LibraryItem | null>(null);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [trimTarget, setTrimTarget] = useState<LibraryItem | null>(null);
  const [backingUpId, setBackingUpId] = useState<string | null>(null);
  const [analysisTarget, setAnalysisTarget] = useState<LibraryItem | null>(null);
  const [isDedupModalOpen, setIsDedupModalOpen] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [addToCollectionItem, setAddToCollectionItem] = useState<LibraryItem | null>(null);

  useEffect(() => {
    fetchLibrary();
    fetchStats();
    fetchUntracked();
    fetchCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== search) {
        setSearch(searchInput);
      }
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput, setSearch]);

  const handleRename = async (id: string, newName: string) => {
    await renameItem(id, newName);
    fetchLibrary(page, platform, search, category);
    fetchStats();
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteItem(deleteTarget.id);
    fetchLibrary(page, platform, search, category);
    fetchStats();
    fetchUntracked();
    fetchCategories();
  };

  const handleImportAll = async () => {
    if (untracked.length === 0) return;
    const paths = untracked.map((u) => u.path);
    await importUntracked(paths);
  };

  const handleTrim = (item: LibraryItem) => {
    setTrimTarget(item);
  };

  const handleBackup = async (id: string) => {
    setBackingUpId(id);
    try {
      await backupDownload(id);
      addToast('Backup started', 'success');
      fetchLibrary(page, platform, search, category);
    } catch {
      addToast('Failed to start backup', 'error');
    } finally {
      setBackingUpId(null);
    }
  };

  const handleAnalysis = (item: LibraryItem) => {
    setAnalysisTarget(item);
  };

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleAddToCollection = (item: LibraryItem) => {
    setAddToCollectionItem(item);
    setIsAddModalOpen(true);
  };

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleAddSuccess = useCallback(async () => {
    setIsAddModalOpen(false);
    setAddToCollectionItem(null);
    await fetchLibrary(page, platform, search, category);
  }, [fetchLibrary, page, platform, search, category]);

  const handleFindDuplicates = useCallback(async () => {
    clearReport();
    setIsDedupModalOpen(true);
    await startScan();
  }, [startScan, clearReport]);

  useEffect(() => {
    if (!scanning || !isDedupModalOpen) return;
    fetchReport();
    const interval = setInterval(() => {
      fetchReport();
    }, 3000);
    return () => clearInterval(interval);
  }, [scanning, isDedupModalOpen, fetchReport]);

  const handleCleanupComplete = useCallback(async (deletedCount: number) => {
    addToast(`Deleted ${deletedCount} duplicate(s)`, 'success');
    await fetchLibrary(page, platform, search, category);
    await fetchStats();
    await fetchUntracked();
    await fetchCategories();
  }, [page, platform, search, category, fetchLibrary, fetchStats, fetchUntracked, fetchCategories, addToast]);

  const handleCloseDedupModal = useCallback(() => {
    setIsDedupModalOpen(false);
  }, []);

  const topPlatform = useMemo(() => {
    if (!stats || stats.platform_breakdown.length === 0) return null;
    return stats.platform_breakdown[0];
  }, [stats]);

  const last7DaysCount = useMemo(() => {
    if (!stats) return 0;
    return stats.downloads_last_7_days.reduce((sum, day) => sum + day.count, 0);
  }, [stats]);

  const chartData = useMemo(() => {
    if (!stats) return [];
    return stats.downloads_last_7_days.map((d) => ({
      date: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
      count: d.count,
    }));
  }, [stats]);

  const platformChartData = useMemo(() => {
    if (!stats) return [];
    return stats.platform_breakdown.map((p: PlatformStat, i) => ({
      name: p.platform,
      value: p.count,
      color: CHART_COLORS[i % CHART_COLORS.length],
    }));
  }, [stats]);

  return (
    <div className="max-w-7xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Media Library</h1>
        <p className="text-text-secondary">Browse and manage your downloaded media</p>
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

      {untracked.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-gradient-to-r from-accent-primary/20 to-accent-secondary/20 border border-accent-primary/30 flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-accent-primary" />
            <span className="text-text-primary font-medium">
              {untracked.length} file{untracked.length !== 1 ? 's' : ''} detected outside library
            </span>
          </div>
          <button
            onClick={handleImportAll}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Import All
          </button>
        </motion.div>
      )}

      {isStatsLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="glass-card rounded-xl p-6 animate-pulse">
              <div className="h-4 bg-bg-tertiary rounded w-1/2 mb-3" />
              <div className="h-8 bg-bg-tertiary rounded w-1/3" />
            </div>
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <Film className="w-5 h-5 text-accent-primary" />
              <span className="text-text-secondary text-sm">Total Videos</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{stats.total_files}</p>
          </motion.div>
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <HardDrive className="w-5 h-5 text-accent-secondary" />
              <span className="text-text-secondary text-sm">Storage Used</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{formatBytes(stats.total_size_bytes)}</p>
          </motion.div>
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-5 h-5 text-status-success" />
              <span className="text-text-secondary text-sm">Top Platform</span>
            </div>
            <div className="flex items-center gap-2">
              {topPlatform && (
                <>
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: PLATFORM_COLORS[topPlatform.platform] || '#888' }}
                  />
                  <p className="text-xl font-bold text-text-primary capitalize">{topPlatform.platform}</p>
                </>
              )}
            </div>
          </motion.div>
          <motion.div whileHover={{ scale: 1.02 }} className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <Download className="w-5 h-5 text-status-warning" />
              <span className="text-text-secondary text-sm">Last 7 Days</span>
            </div>
            <p className="text-3xl font-bold text-text-primary">{last7DaysCount}</p>
          </motion.div>
        </div>
      ) : null}

      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 glass-card rounded-xl p-6">
            <h3 className="text-text-primary font-semibold mb-4">Downloads (Last 7 Days)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6C5CE7" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00D2FF" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#A0A0B0', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#A0A0B0', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(18, 18, 26, 0.9)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                />
                <Area type="monotone" dataKey="count" stroke="url(#colorCount)" fill="url(#colorCount)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="glass-card rounded-xl p-6">
            <h3 className="text-text-primary font-semibold mb-4">Platform Breakdown</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={platformChartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {platformChartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(18, 18, 26, 0.9)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-2 mt-4">
              {platformChartData.map((entry) => (
                <div key={entry.name} className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                  <span className="text-xs text-text-secondary capitalize">{entry.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="glass-card rounded-xl p-6 mb-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search media..."
              className="w-full pl-10 pr-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
            />
          </div>
          <button
            onClick={handleFindDuplicates}
            disabled={scanning}
            className="px-4 py-2.5 rounded-lg bg-bg-tertiary border border-border text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
          >
            {scanning ? (
              <>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
                  className="w-4 h-4 rounded-full border-2 border-accent-primary border-t-transparent"
                />
                Scanning...
              </>
            ) : (
              <>
                <CopyX className="w-4 h-4" />
                Find Duplicates
              </>
            )}
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setCategory('')}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              category === '' ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white' : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
            }`}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat.category}
              onClick={() => setCategory(cat.category)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium capitalize transition-all ${
                category === cat.category ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white' : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
              }`}
            >
              {cat.category} <span className="text-xs opacity-75">({cat.count})</span>
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="glass-card rounded-xl overflow-hidden animate-pulse">
                <div className="aspect-video bg-bg-tertiary" />
                <div className="p-4">
                  <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-2" />
                  <div className="h-3 bg-bg-tertiary rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <Film className="w-16 h-16 text-text-muted mx-auto mb-4" />
            <h3 className="text-text-primary text-xl font-semibold mb-2">No media found</h3>
            <p className="text-text-secondary">
              {search || platform || category ? 'Try adjusting your search or filters' : 'Your library is empty. Start downloading some videos!'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {items.map((item) => (
              <MediaCard
                key={item.id}
                item={item}
                onPreview={(libItem) => {
                  setSelectedItem(libItem);
                }}
                onOpenFolder={(id) => openFolder(id)}
                onRename={(libItem) => {
                  setRenameTarget(libItem);
                  setIsRenameModalOpen(true);
                }}
                onDelete={(libItem) => {
                  setDeleteTarget(libItem);
                  setIsDeleteDialogOpen(true);
                }}
                onTrim={handleTrim}
                onBackup={handleBackup}
                isBackingUp={backingUpId === item.id}
                onAnalysis={handleAnalysis}
                onAddToCollection={() => handleAddToCollection(item)}
              />
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-8">
            <button
              onClick={() => setPage(page - 1)}
              disabled={page === 1}
              className="px-4 py-2 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
            >
              Previous
            </button>
            <span className="text-text-secondary text-sm">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!hasNext}
              className="px-4 py-2 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>

      <MediaPreviewModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onAddToCollection={selectedItem ? () => handleAddToCollection(selectedItem) : undefined}
      />
      <RenameModal
        item={renameTarget}
        isOpen={isRenameModalOpen}
        onClose={() => setIsRenameModalOpen(false)}
        onRename={handleRename}
      />
      <DeleteConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => setIsDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        title="Delete Media"
        message={`Are you sure you want to delete "${deleteTarget?.title}"? This action cannot be undone.`}
      />
      <TrimmerModal
        isOpen={!!trimTarget}
        onClose={() => setTrimTarget(null)}
        item={trimTarget || undefined}
      />
      <AnalysisModal
        isOpen={!!analysisTarget}
        onClose={() => setAnalysisTarget(null)}
        item={analysisTarget || undefined}
      />
      <DedupReportModal
        isOpen={isDedupModalOpen}
        onClose={handleCloseDedupModal}
        onCleanupComplete={handleCleanupComplete}
      />
      <AddToCollectionModal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false);
          setAddToCollectionItem(null);
        }}
        downloadIds={addToCollectionItem ? [addToCollectionItem.id] : []}
        onSuccess={handleAddSuccess}
      />
    </div>
  );
}

