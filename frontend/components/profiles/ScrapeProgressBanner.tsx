'use client';
import { useEffect } from 'react';
import { useProfileStore } from '@/lib/store/profiles';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';

export function ScrapeProgressBanner({ profileId }: { profileId: string }) {
  const { isScraping, scrapeProgress, subscribeScrapeProgress, fetchProfileDetail } = useProfileStore();

  useEffect(() => {
    if (isScraping) {
      subscribeScrapeProgress(profileId);
    }
  }, [isScraping, profileId, subscribeScrapeProgress]);

  useEffect(() => {
    if (scrapeProgress?.status === 'completed') {
      fetchProfileDetail(profileId);
    }
  }, [scrapeProgress?.status, profileId, fetchProfileDetail]);

  return (
    <AnimatePresence>
      {isScraping && scrapeProgress && (
        <motion.div initial={{ opacity: 0, y: -20, height: 0 }} animate={{ opacity: 1, y: 0, height: 'auto' }} exit={{ opacity: 0, scale: 0.95, height: 0 }} className="mb-6 p-4 rounded-xl border border-blue-500/30 bg-blue-500/10 flex flex-col sm:flex-row items-center justify-between relative overflow-hidden gap-4">
          <div className="flex items-center gap-3 relative z-10">
            <Loader2 className="animate-spin text-blue-400" size={20} />
            <h3 className="text-blue-100 font-medium">Scraping Profile in progress...</h3>
          </div>
          <div className="flex items-center gap-6 text-sm relative z-10">
            <p className="text-gray-300">Discovered: <span className="text-white font-bold">{scrapeProgress.discovered}</span></p>
            <p className="text-gray-300">New Videos: <span className="text-green-400 font-bold">{scrapeProgress.new_count}</span></p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

