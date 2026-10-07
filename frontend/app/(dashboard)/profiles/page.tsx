'use client';
import { useEffect, useState } from 'react';
import { useProfileStore } from '@/lib/store/profiles';
import { ProfileCard } from '@/components/profiles/ProfileCard';
import { motion } from 'framer-motion';
import ScheduleModal from '@/components/scheduler/ScheduleModal';
import { CalendarClock, ListPlus } from 'lucide-react';
import { BulkImportModal } from '@/components/bulk/BulkImportModal';
import { FeatureGuard } from '@/components/feature/FeatureGuard';

export default function ProfilesPage() {
  const { profiles, fetchProfiles, removeProfile, startScrape } = useProfileStore();
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  return (
    <FeatureGuard featureKey="profiles">
      <div className="p-8 max-w-7xl mx-auto w-full">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">Creator Profiles</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBulkModal(true)}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary hover:from-accent-primary/90 hover:to-accent-secondary/90 text-white text-sm font-medium flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(108,92,231,0.4)]"
          >
            <ListPlus className="w-4 h-4" />
            Bulk Import
          </button>
          <button
            onClick={() => setShowScheduleModal(true)}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-400 hover:to-pink-500 text-white text-sm font-medium flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(147,51,234,0.4)]"
          >
            <CalendarClock className="w-4 h-4" />
            Schedule Downloads
          </button>
        </div>
      </div>

      {profiles.length === 0 ? (
        <div className="text-center py-20 glass-card rounded-2xl border border-white/5">
          <h2 className="text-xl text-gray-400">No profiles yet - paste a creator&apos;s link on the Home page to get started.</h2>
        </div>
      ) : (
        <motion.div initial="hidden" animate="visible" variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { staggerChildren: 0.1 } } }} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {profiles.map(p => (
            <ProfileCard key={p.id} profile={p} onDelete={removeProfile} onRescrape={(url) => startScrape(url, 50)} />
          ))}
        </motion.div>
      )}

      <ScheduleModal
        isOpen={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
        profileId=""
      />
      <BulkImportModal isOpen={showBulkModal} onClose={() => setShowBulkModal(false)} />
      </div>
    </FeatureGuard>
  );
}
