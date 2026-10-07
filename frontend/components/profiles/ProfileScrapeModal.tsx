'use client';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useProfileStore } from '@/lib/store/profiles';
import { QUALITY_PRESETS } from '@/lib/constants/quality-presets';
import { useRouter } from 'next/navigation';
import { getPlatformFromUrl } from '@/lib/utils/url';
import { X, UserPlus, Play } from 'lucide-react';

export function ProfileScrapeModal({ url, onClose }: { url: string; onClose: () => void }) {
  const platform = getPlatformFromUrl(url);
  const [limit, setLimit] = useState<number>(50);
  const [quality, setQuality] = useState<string>('best');
  const { startScrape, setQuality: saveQualityPreference } = useProfileStore();
  const router = useRouter();

  const handleStart = async () => {
    try {
      saveQualityPreference(quality);
      await startScrape(url, limit);
      router.push('/profiles'); // In a complete flow, we'd navigate to the exact /profiles/[id] 
      onClose();
    } catch {
      alert("Failed to start scrape");
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 20 }} className="glass-card w-full max-w-md rounded-2xl border border-white/10 overflow-hidden relative shadow-2xl">
          
          <div className={`h-1.5 w-full ${platform}-glow bg-white/20`} />
          
          <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>

          <div className="p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className={`p-3 rounded-xl bg-white/5 border border-white/10 text-${platform}`}>
                <UserPlus size={24} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Scrape Profile</h2>
                <p className="text-sm text-gray-400">Extract videos from this creator</p>
              </div>
            </div>

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Target URL</label>
                <div className="p-3 bg-black/40 border border-white/10 rounded-lg text-sm text-gray-400 truncate">
                  {url}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Video Limit</label>
                <input type="range" min="10" max="200" step="10" value={limit} onChange={(e) => setLimit(parseInt(e.target.value))} className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500" />
                <div className="flex justify-between text-xs text-gray-500 mt-2">
                  <span>10</span><span className="text-blue-400 font-medium">{limit} videos</span><span>200</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Download Quality</label>
                <select value={quality} onChange={(e) => setQuality(e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-white text-sm outline-none focus:border-blue-500 transition">
                  {QUALITY_PRESETS.map(q => (
                    <option key={q.value} value={q.value}>{q.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <button onClick={handleStart} className="w-full mt-8 py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-400 hover:to-purple-500 text-white font-medium flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(59,130,246,0.5)]">
              <Play size={18} fill="currentColor" /> Start Extraction
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
