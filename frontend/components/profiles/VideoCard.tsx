'use client';
import { ProfileVideo } from '@/lib/api/profiles';
import { motion } from 'framer-motion';
import { AlertCircle, Clock, Check } from 'lucide-react';

const statusColors: Record<string, string> = {
  new: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  queued: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  downloaded: 'bg-green-500/20 text-green-400 border-green-500/30',
  skipped: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30'
};

export function VideoCard({ video, selected, onSelect }: { video: ProfileVideo; selected: boolean; onSelect: () => void }) {
  const showCheckbox = video.status === 'new' || video.status === 'failed';
  
  return (
    <motion.div variants={{ hidden: { scale: 0.95, opacity: 0 }, visible: { scale: 1, opacity: 1 } }} whileHover={{ scale: 1.02 }} className={`glass-card rounded-xl overflow-hidden relative group border ${selected ? 'border-blue-500' : 'border-white/5'} transition-all cursor-pointer`} onClick={() => showCheckbox && onSelect()}>
      <div className="relative aspect-video bg-black/40">
        {video.thumbnail_url ? <img src={video.thumbnail_url} alt="thumbnail" className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" /> : <div className="w-full h-full flex items-center justify-center text-gray-600"><AlertCircle /></div>}
        <div className="absolute top-2 left-2 flex gap-2">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border backdrop-blur-md ${statusColors[video.status]}`}>{video.status.toUpperCase()}</span>
        </div>
        {showCheckbox && (
          <div className="absolute top-2 right-2 w-5 h-5 rounded border border-white/20 bg-black/40 flex items-center justify-center">
            {selected && <Check size={14} className="text-blue-400" />}
          </div>
        )}
      </div>
      <div className="p-3">
        <h4 className="text-sm text-gray-200 line-clamp-2 leading-snug">{video.title || video.video_url}</h4>
        <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
          <Clock size={12} /> {video.upload_date || 'Unknown date'}
        </div>
      </div>
    </motion.div>
  );
}
