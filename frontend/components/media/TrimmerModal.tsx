'use client';

import { LibraryItem } from '@/lib/api/library';
import { createDownload, CreateDownloadRequest } from '@/lib/api/downloads';
import { X, Scissors, Play, Pause, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface TrimmerModalProps {
  isOpen: boolean;
  onClose: () => void;
  item?: LibraryItem;
  streamUrl?: string;
}

export function TrimmerModal({ isOpen, onClose, item, streamUrl }: TrimmerModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(0);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState<{ id: string; message: string; type: 'success' | 'error' } | null>(null);

  const fileUrl = item
    ? `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/downloads/${item.id}/file`
    : streamUrl || '';

  useEffect(() => {
    if (isOpen) {
      setIsPlaying(false);
      setError('');
      setStartTime(0);
      setEndTime(0);
      setCurrentTime(0);
      setDuration(0);
      setToast(null);
    }
  }, [isOpen]);

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (video) {
      const dur = video.duration;
      setDuration(dur);
      setEndTime(dur);
    }
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (video) {
      setCurrentTime(video.currentTime);
      if (video.currentTime >= endTime && isPlaying) {
        video.pause();
        video.currentTime = startTime;
        setIsPlaying(false);
      }
    }
  };

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play();
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    if (val >= endTime) {
      setError('Start time must be before end time');
      return;
    }
    setError('');
    setStartTime(val);
    if (videoRef.current) videoRef.current.currentTime = val;
  };

  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    if (val <= startTime) {
      setError('End time must be after start time');
      return;
    }
    setError('');
    setEndTime(val);
  };

  const setFirst30s = () => {
    if (duration <= 0) return;
    const end = Math.min(30, duration);
    setStartTime(0);
    setEndTime(end);
    setError('');
  };

  const setLast30s = () => {
    if (duration <= 0) return;
    const start = Math.max(0, duration - 30);
    setStartTime(start);
    setEndTime(duration);
    setError('');
  };

  const setFullVideo = () => {
    setStartTime(0);
    setEndTime(duration);
    setError('');
  };

  const showToast = (message: string, type: 'success' | 'error') => {
    const id = Math.random().toString(36).slice(2, 9);
    setToast({ id, message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleDownload = async () => {
    if (endTime <= startTime) {
      setError('End time must be greater than start time');
      return;
    }
    setIsSubmitting(true);
    try {
      const url = item ? undefined : streamUrl;
      if (!url && !item) {
        setError('No URL provided');
        setIsSubmitting(false);
        return;
      }

      const payload: CreateDownloadRequest = {
        url: url || item?.file_path || '',
        start_time: formatTime(startTime),
        end_time: formatTime(endTime),
      };

      await createDownload(payload);
      showToast('Trimmed download added to queue', 'success');
      onClose();
    } catch {
      showToast('Failed to create trimmed download', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const startPercent = duration > 0 ? (startTime / duration) * 100 : 0;
  const endPercent = duration > 0 ? (endTime / duration) * 100 : 100;
  const selectedDuration = endTime - startTime;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="glass-card rounded-xl p-6 w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-text-primary flex items-center gap-2">
                <Scissors className="w-5 h-5 text-accent-primary" />
                Trim Video
              </h2>
              <button
                onClick={onClose}
                className="p-2 rounded-full hover:bg-bg-tertiary text-text-secondary transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="relative bg-black rounded-lg overflow-hidden mb-4">
              <video
                ref={videoRef}
                src={fileUrl}
                className="w-full max-h-[50vh]"
                onLoadedMetadata={handleLoadedMetadata}
                onTimeUpdate={handleTimeUpdate}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={() => setIsPlaying(false)}
                playsInline
              />
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
                <div className="flex items-center justify-between text-white">
                  <button
                    onClick={togglePlay}
                    className="p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                  >
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </button>
                  <span className="text-xs font-mono text-text-secondary">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>
              </div>
            </div>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono text-text-secondary">Start: {formatTime(startTime)}</span>
                <span className="text-xs font-mono text-text-secondary">End: {formatTime(endTime)}</span>
              </div>

              <div className="dual-range relative w-full h-8 flex items-center select-none">
                <div className="absolute w-full h-2 bg-bg-tertiary rounded-full" />
                <div
                  className="absolute h-2 rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary"
                  style={{ left: `${startPercent}%`, width: `${endPercent - startPercent}%` }}
                />
                <input
                  type="range"
                  min={0}
                  max={duration || 0}
                  step={0.1}
                  value={startTime}
                  onChange={handleStartChange}
                  className="dual-range-input absolute w-full h-full appearance-none bg-transparent cursor-pointer"
                  style={{ zIndex: startTime > duration / 2 ? 1 : 3 }}
                />
                <input
                  type="range"
                  min={0}
                  max={duration || 0}
                  step={0.1}
                  value={endTime}
                  onChange={handleEndChange}
                  className="dual-range-input absolute w-full h-full appearance-none bg-transparent cursor-pointer"
                  style={{ zIndex: startTime > duration / 2 ? 3 : 1 }}
                />
                <div
                  className="dual-range-thumb absolute top-1/2 -translate-y-1/2 w-6 h-6 bg-white rounded-full shadow-lg border-2 border-accent-primary"
                  style={{ left: `calc(${startPercent}% - 12px)` }}
                />
                <div
                  className="dual-range-thumb absolute top-1/2 -translate-y-1/2 w-6 h-6 bg-white rounded-full shadow-lg border-2 border-accent-primary"
                  style={{ left: `calc(${endPercent}% - 12px)` }}
                />
              </div>

              <div className="flex items-center justify-between mt-3">
                <span className={`text-xs font-mono ${error ? 'text-status-error' : 'text-text-secondary'}`}>
                  Selected: {formatTime(selectedDuration)}
                </span>
                {error && <span className="text-xs text-status-error">{error}</span>}
              </div>
            </div>

            <div className="flex gap-2 mb-6">
              <button
                onClick={setFirst30s}
                className="px-3 py-1.5 rounded-lg bg-bg-tertiary text-text-secondary text-xs font-medium hover:text-text-primary transition-colors"
              >
                First 30s
              </button>
              <button
                onClick={setLast30s}
                className="px-3 py-1.5 rounded-lg bg-bg-tertiary text-text-secondary text-xs font-medium hover:text-text-primary transition-colors"
              >
                Last 30s
              </button>
              <button
                onClick={setFullVideo}
                className="px-3 py-1.5 rounded-lg bg-bg-tertiary text-text-secondary text-xs font-medium hover:text-text-primary transition-colors"
              >
                Full Video
              </button>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDownload}
                disabled={isSubmitting || !!error || endTime <= startTime || duration <= 0}
                className="px-6 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <RotateCcw className="w-4 h-4 animate-spin" />
                    Downloading...
                  </>
                ) : (
                  <>
                    <Scissors className="w-4 h-4" />
                    Download Section
                  </>
                )}
              </button>
            </div>

            <AnimatePresence>
              {toast && (
                <motion.div
                  key={toast.id}
                  initial={{ opacity: 0, y: 20, x: '-50%' }}
                  animate={{ opacity: 1, y: 0, x: '-50%' }}
                  exit={{ opacity: 0, y: 20, x: '-50%' }}
                  className={`fixed top-4 left-1/2 z-[60] px-6 py-3 rounded-lg shadow-lg ${
                    toast.type === 'success' ? 'bg-status-success' : 'bg-status-error'
                  } text-white`}
                >
                  {toast.message}
                  <button onClick={() => setToast(null)} className="ml-3 hover:opacity-80">
                    <X className="w-4 h-4" />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
