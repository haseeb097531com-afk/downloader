'use client';

import { useEffect, useState } from 'react';
import { useSearchStore } from '@/lib/store/search';
import { SearchBar } from '@/components/search/SearchBar';
import { FilterPanel } from '@/components/search/FilterPanel';
import { MediaCard } from '@/components/media/MediaCard';
import { MediaPreviewModal } from '@/components/media/MediaPreviewModal';
import { SearchResultItem } from '@/lib/api/search';
import { Bookmark, X, ChevronLeft, ChevronRight, SlidersHorizontal, Search as SearchIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { AddToCollectionModal } from '@/components/collections/AddToCollectionModal';

export default function SearchPage() {
  const {
    query,
    filters,
    sort,
    page,
    results,
    savedSearches,
    isLoading,
    isSavingSearch,
    setQuery,
    setFilters,
    setSort,
    setPage,
    saveSearch,
    removeSavedSearch,
    loadSavedSearches,
    applySavedSearch,
    toasts,
    dismissToast,
  } = useSearchStore();

  const [selectedItem, setSelectedItem] = useState<SearchResultItem | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addToCollectionItem, setAddToCollectionItem] = useState<SearchResultItem | null>(null);

  useEffect(() => {
    loadSavedSearches();
  }, [loadSavedSearches]);

  const facets = results?.facets || { platforms: [], categories: [] };

  const handleSave = async () => {
    if (!saveName.trim()) return;
    await saveSearch(saveName.trim());
    setSaveName('');
    setIsSaveModalOpen(false);
  };

  const handleAddToCollection = (item: SearchResultItem) => {
    setAddToCollectionItem(item);
    setIsAddModalOpen(true);
  };

  const handleAddSuccess = async () => {
    setIsAddModalOpen(false);
    setAddToCollectionItem(null);
  };

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Search</h1>
        <p className="text-text-secondary">Find media across your library</p>
      </div>

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

      <div className="space-y-4 mb-6">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSave={() => setIsSaveModalOpen(true)}
        />

        {savedSearches.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {savedSearches.map((saved) => (
              <div
                key={saved.id}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
              >
                <button
                  onClick={() => applySavedSearch(saved)}
                  className="flex items-center gap-2 text-sm"
                >
                  <Bookmark className="w-3.5 h-3.5" />
                  {saved.name}
                </button>
                <button
                  onClick={() => removeSavedSearch(saved.id)}
                  className="text-text-muted hover:text-status-error"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="lg:grid lg:grid-cols-[280px_1fr] lg:gap-6">
        <div className="hidden lg:block">
          <FilterPanel
            filters={filters}
            facets={facets}
            sort={sort}
            onFiltersChange={setFilters}
            onSortChange={setSort}
          />
        </div>

        <div className="lg:hidden mb-4">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg glass-card text-text-primary"
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filters
            {(filters.platforms?.length || filters.categories?.length || filters.quality || filters.date_from || filters.date_to || filters.watermark_free || filters.cloud_backed || filters.include_quarantined) && (
              <span className="px-2 py-0.5 rounded-full bg-accent-primary/20 text-accent-primary text-xs">
                Active
              </span>
            )}
          </button>
          {showFilters && (
            <div className="mt-4">
              <FilterPanel
                filters={filters}
                facets={facets}
                sort={sort}
                onFiltersChange={(f) => {
                  setFilters(f);
                }}
                onSortChange={setSort}
                onClose={() => setShowFilters(false)}
              />
            </div>
          )}
        </div>

        <div>
          {!query && (
            <div className="text-center py-20">
              <SearchIcon className="w-16 h-16 text-text-muted mx-auto mb-4" />
              <h3 className="text-text-primary text-xl font-semibold mb-2">Start searching</h3>
              <p className="text-text-secondary">Enter a query to search across your media library</p>
            </div>
          )}

          {query && !isLoading && results && results.items.length === 0 && (
            <div className="text-center py-20">
              <SearchIcon className="w-16 h-16 text-text-muted mx-auto mb-4" />
              <h3 className="text-text-primary text-xl font-semibold mb-2">No matches</h3>
              <p className="text-text-secondary">Try fewer filters or a different search term</p>
            </div>
          )}

          {isLoading && (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
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
          )}

          {!isLoading && results && results.items.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-text-secondary text-sm">
                  {results.total} result{results.total !== 1 ? 's' : ''} found
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                {results.items.map((item) => (
                  <MediaCard
                    key={item.id}
                    item={{ ...item, metadata_json: null }}
                    onPreview={(libItem) => setSelectedItem(libItem)}
                    onOpenFolder={() => {}}
                    onRename={() => {}}
                    onDelete={() => {}}
                    onAddToCollection={() => handleAddToCollection(item)}
                  />
                ))}
              </div>

              {results.total_pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-8">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="p-2 rounded-lg glass-card text-text-secondary hover:text-text-primary disabled:opacity-50"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <span className="text-text-secondary text-sm">
                    Page {page} of {results.total_pages}
                  </span>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page >= results.total_pages}
                    className="p-2 rounded-lg glass-card text-text-secondary hover:text-text-primary disabled:opacity-50"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <AnimatePresence>
        {isSaveModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => setIsSaveModalOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card rounded-xl p-6 w-full max-w-md mx-4"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-text-primary text-lg font-semibold mb-4">Save Search</h2>
              <input
                type="text"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="Search name"
                className="w-full px-4 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent-primary mb-4"
                autoFocus
              />
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setIsSaveModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSavingSearch || !saveName.trim()}
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium disabled:opacity-50"
                >
                  {isSavingSearch ? 'Saving...' : 'Save'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <MediaPreviewModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onAddToCollection={selectedItem ? () => handleAddToCollection(selectedItem) : undefined}
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
