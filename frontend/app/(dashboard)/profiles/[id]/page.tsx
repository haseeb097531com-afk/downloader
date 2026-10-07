'use client';
import { useEffect, useState } from 'react';
import { useProfileStore } from '@/lib/store/profiles';
import { useScheduleStore } from '@/lib/store/schedules';
import { ProfileHeader } from '@/components/profiles/ProfileHeader';
import { VideoGrid } from '@/components/profiles/VideoGrid';
import { ScrapeProgressBanner } from '@/components/profiles/ScrapeProgressBanner';
import ScheduleModal from '@/components/scheduler/ScheduleModal';
import { CalendarClock, Plus } from 'lucide-react';
import { motion } from 'framer-motion';
import { Schedule } from '@/lib/api/schedules';

export default function ProfileDetailPage({ params }: { params: { id: string } }) {
  const { activeProfile, fetchProfileDetail, clearSelection } = useProfileStore();
  const { schedules, fetchSchedules } = useScheduleStore();
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);

  const profileSchedules = schedules.filter((s) => s.profile_id === params.id);

  useEffect(() => {
    fetchProfileDetail(params.id);
    fetchSchedules();
    return () => clearSelection();
  }, [params.id, fetchProfileDetail, clearSelection, fetchSchedules]);

  if (!activeProfile) return (
    <div className="p-8 max-w-7xl mx-auto w-full flex items-center justify-center min-h-[50vh]">
      <div className="animate-pulse flex flex-col items-center gap-4 text-gray-500">
        <div className="w-16 h-16 border-4 border-white/10 border-t-blue-500 rounded-full animate-spin"></div>
        <p>Loading profile...</p>
      </div>
    </div>
  );

  return (
    <div className="p-8 max-w-7xl mx-auto w-full">
      <ScrapeProgressBanner profileId={params.id} />
      <ProfileHeader profile={activeProfile} />

      {profileSchedules.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 glass-card rounded-xl p-6 border border-white/5"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-primary/20">
                <CalendarClock className="w-5 h-5 text-accent-primary" />
              </div>
              <div>
                <h3 className="text-text-primary font-semibold">Active Schedules</h3>
                <p className="text-text-secondary text-sm">{profileSchedules.length} schedule{profileSchedules.length !== 1 ? 's' : ''} configured</p>
              </div>
            </div>
            <button
              onClick={() => { setEditingSchedule(null); setShowScheduleModal(true); }}
              className="px-3 py-1.5 rounded-lg bg-bg-tertiary border border-white/10 text-text-secondary hover:text-text-primary text-sm font-medium transition-colors flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Schedule
            </button>
          </div>
          <div className="space-y-3">
            {profileSchedules.map((schedule) => (
              <div
                key={schedule.id}
                className="flex items-center justify-between p-4 rounded-lg bg-bg-tertiary/50 border border-border"
              >
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full ${schedule.is_active ? 'bg-status-success animate-pulse' : 'bg-text-muted'}`} />
                  <div>
                    <p className="text-text-primary font-medium capitalize">{schedule.frequency}</p>
                    <p className="text-text-secondary text-xs">
                      {schedule.time_of_day} | Quality: {schedule.quality}
                      {schedule.frequency === 'weekly' && schedule.days_of_week && schedule.days_of_week.length > 0 && ` | ${schedule.days_of_week.map(d => d.slice(0, 3)).join(', ')}`}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => { setEditingSchedule(schedule); setShowScheduleModal(true); }}
                  className="px-3 py-1.5 rounded-lg bg-bg-tertiary border border-white/10 text-text-secondary hover:text-text-primary text-xs font-medium transition-colors"
                >
                  Edit Schedule
                </button>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {profileSchedules.length === 0 && (
        <div className="mt-6 glass-card rounded-xl p-6 border border-white/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-bg-tertiary/50">
                <CalendarClock className="w-5 h-5 text-text-muted" />
              </div>
              <div>
                <h3 className="text-text-primary font-medium">No Active Schedules</h3>
                <p className="text-text-secondary text-sm">Set up automatic scraping for this profile</p>
              </div>
            </div>
            <button
              onClick={() => { setEditingSchedule(null); setShowScheduleModal(true); }}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-400 hover:to-pink-500 text-white text-sm font-medium flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(147,51,234,0.4)]"
            >
              <Plus className="w-4 h-4" />
              Schedule Downloads
            </button>
          </div>
        </div>
      )}

      <VideoGrid profileId={params.id} />

      <ScheduleModal
        isOpen={showScheduleModal}
        onClose={() => { setShowScheduleModal(false); setEditingSchedule(null); }}
        profileId={params.id}
        existingSchedule={editingSchedule}
      />
    </div>
  );
}
