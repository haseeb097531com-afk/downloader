'use client';
import { useProfileStore } from '@/lib/store/profiles';
import { VideoCard } from './VideoCard';
import { motion } from 'framer-motion';
import { Download, CheckSquare } from 'lucide-react';

export function VideoGrid({ profileId }: { profileId: string }) {
  const { videos, selectedVideoIds, toggleVideoSelection, enqueueDownloads, clearSelection } = useProfileStore();
  
  const newVideos = videos.filter(v => v.status === 'new' || v.status === 'failed');
  const selectedCount = selectedVideoIds.size;

  const handleDownloadAllNew = async () => {
    const ids = newVideos.map(v => v.id);
    if (ids.length > 0) {
      await enqueueDownloads(profileId, ids);
    }
  };

  const handleDownloadSelected = async () => {
    if (selectedCount > 0) {
      await enqueueDownloads(profileId, Array.from(selectedVideoIds));
    }
  };

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4 glass-card p-3 px-4 rounded-xl border border-white/10 sticky top-4 z-20 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <button onClick={handleDownloadAllNew} disabled={newVideos.length === 0} className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition">
            <Download size={16} /> Download All New ({newVideos.length})
          </button>
          <button onClick={handleDownloadSelected} disabled={selectedCount === 0} className="bg-white/5 hover:bg-white/10 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition border border-white/5">
            <CheckSquare size={16} /> Download Selected ({selectedCount})
          </button>
        </div>
        {selectedCount > 0 && (
          <button onClick={clearSelection} className="text-gray-400 hover:text-white text-sm">Clear Selection</button>
        )}
      </div>

      <motion.div initial="hidden" animate="visible" variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { staggerChildren: 0.05 } } }} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {videos.map(video => (
          <VideoCard key={video.id} video={video} selected={selectedVideoIds.has(video.id)} onSelect={() => toggleVideoSelection(video.id)} />
        ))}
      </motion.div>
    </div>
  );
}

