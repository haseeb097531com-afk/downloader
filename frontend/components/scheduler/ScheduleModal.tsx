'use client';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Calendar, Clock, Download, RefreshCw } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { QUALITY_PRESETS, type QualityPreset } from '@/lib/constants/quality-presets';
import { useScheduleStore } from '@/lib/store/schedules';

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const QUALITY_OPTIONS = QUALITY_PRESETS;

interface ScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  profileId: string;
  existingSchedule?: any;
}

export default function ScheduleModal({ isOpen, onClose, profileId, existingSchedule }: ScheduleModalProps) {
  const [frequency, setFrequency] = useState<'daily' | 'weekly' | 'cron'>(existingSchedule?.frequency || 'daily');
  const [timeOfDay, setTimeOfDay] = useState(existingSchedule?.time_of_day || '09:00');
  const [quality, setQuality] = useState(existingSchedule?.quality || 'best');
  const [active, setActive] = useState(existingSchedule?.is_active ?? true);
  const [selectedDays, setSelectedDays] = useState<string[]>(existingSchedule?.days_of_week || []);
  const [cronExpression, setCronExpression] = useState(existingSchedule?.cron_expression || '');
  const [isSaving, setIsSaving] = useState(false);

  const { createSchedule: create, updateSchedule: update, addToast } = useScheduleStore();

  useEffect(() => {
    if (existingSchedule) {
      setFrequency(existingSchedule.frequency);
      setTimeOfDay(existingSchedule.time_of_day);
      setQuality(existingSchedule.quality);
      setActive(existingSchedule.is_active);
      setSelectedDays(existingSchedule.days_of_week || []);
      setCronExpression(existingSchedule.cron_expression || '');
    } else {
      setFrequency('daily');
      setTimeOfDay('09:00');
      setQuality('best');
      setActive(true);
      setSelectedDays([]);
      setCronExpression('');
    }
  }, [existingSchedule, isOpen]);

  const toggleDay = (day: string) => {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );
  };

  const handleSave = async () => {
    if (frequency === 'weekly' && selectedDays.length === 0) {
      addToast('Please select at least one day for weekly schedule', 'error');
      return;
    }
    if (frequency === 'cron' && !cronExpression.trim()) {
      addToast('Please enter a cron expression', 'error');
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        profile_id: profileId,
        frequency,
        time_of_day: timeOfDay,
        quality,
        is_active: active,
        ...(frequency === 'weekly' ? { days_of_week: selectedDays } : {}),
        ...(frequency === 'cron' ? { cron_expression: cronExpression } : {}),
      };

      if (existingSchedule) {
        await update(existingSchedule.id, payload);
      } else {
        await create(payload);
      }
      onClose();
    } catch {
      // toast handled by store
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 20 }}
            className="glass-card w-full max-w-lg rounded-2xl border border-white/10 overflow-hidden relative shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="h-1.5 w-full bg-gradient-to-r from-blue-500 to-purple-600" />

            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-white/5 border border-white/10">
                    <Calendar className="w-6 h-6 text-blue-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">
                      {existingSchedule ? 'Edit Schedule' : 'Schedule Downloads'}
                    </h2>
                    <p className="text-sm text-gray-400">
                      {existingSchedule ? 'Update schedule settings' : 'Set up automatic profile scraping'}
                    </p>
                  </div>
                </div>
                <button onClick={onClose} className="text-gray-400 hover:text-white transition">
                  <X size={20} />
                </button>
              </div>

              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Frequency</label>
                  <div className="flex gap-2">
                    {(['daily', 'weekly', 'cron'] as const).map((freq) => (
                      <button
                        key={freq}
                        onClick={() => setFrequency(freq)}
                        className={`flex-1 py-2.5 rounded-lg text-sm font-medium capitalize transition-all ${
                          frequency === freq
                            ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                            : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        {freq}
                      </button>
                    ))}
                  </div>
                </div>

                {frequency === 'weekly' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Days of Week</label>
                    <div className="flex flex-wrap gap-2">
                      {DAYS.map((day) => {
                        const isSelected = selectedDays.includes(day);
                        return (
                          <button
                            key={day}
                            onClick={() => toggleDay(day)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                              isSelected
                                ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                                : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            {day.slice(0, 3)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {frequency === 'cron' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Cron Expression</label>
                    <input
                      type="text"
                      value={cronExpression}
                      onChange={(e) => setCronExpression(e.target.value)}
                      placeholder="0 9 * * *"
                      className="w-full px-4 py-2.5 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm placeholder:text-text-muted focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <p className="text-xs text-text-muted mt-1.5">Format: minute hour day month weekday</p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Time</label>
                  <div className="relative">
                    <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                      type="time"
                      value={timeOfDay}
                      onChange={(e) => setTimeOfDay(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Quality Preference</label>
                  <div className="relative">
                    <Download className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <select
                      value={quality}
                      onChange={(e) => setQuality(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors appearance-none"
                    >
                      {QUALITY_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-text-primary font-medium">Active</p>
                    <p className="text-text-secondary text-sm mt-0.5">
                      {active ? 'Schedule is running' : 'Schedule is paused'}
                    </p>
                  </div>
                  <Switch checked={active} onCheckedChange={setActive} />
                </div>
              </div>

              <div className="flex gap-3 mt-8">
                <button
                  onClick={onClose}
                  className="flex-1 py-3 px-4 rounded-xl bg-bg-tertiary border border-white/10 text-text-secondary hover:text-text-primary font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-400 hover:to-purple-500 text-white font-medium flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(59,130,246,0.5)] disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }} className="w-4 h-4 rounded-full border-2 border-white border-t-transparent" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={16} />
                      {existingSchedule ? 'Update' : 'Save'} Schedule
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
