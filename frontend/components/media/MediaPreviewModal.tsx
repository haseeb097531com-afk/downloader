'use client';

import { LibraryItem } from '@/lib/api/library';
import { X, Play, Pause, Volume2, VolumeX, Maximize, FolderPlus } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface MediaPreviewModalProps {
  item: LibraryItem | null;
  onClose: () => void;
  onAddToCollection?: (item: LibraryItem) => void;
}

export function MediaPreviewModal({ item, onClose, onAddToCollection }: MediaPreviewModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showVolumeSlider, setShowVolumeSlider] = useState(false);

  useEffect(() => {
    if (item && videoRef.current) {
      videoRef.current.load();
      setIsPlaying(false);
      setCurrentTime(0);
      setDuration(0);
    }
  }, [item]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

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

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (video) setCurrentTime(video.currentTime);
  };

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (video) setDuration(video.duration);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (video) {
      const time = Number(e.target.value);
      video.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    const newVolume = Number(e.target.value);
    setVolume(newVolume);
    if (video) video.volume = newVolume;
    setIsMuted(newVolume === 0);
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;
    if (isMuted) {
      video.volume = volume || 1;
      setIsMuted(false);
    } else {
      video.volume = 0;
      setIsMuted(true);
    }
  };

  const toggleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      video.requestFullscreen();
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const fileUrl = item ? `${process.env.NEXT_PUBLIC_API_URL || '/api/v1'}/downloads/${item.id}/file` : '';

  return (
    <AnimatePresence>
      {item && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="relative w-full max-w-5xl mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute -top-10 right-0 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors z-10"
            >
              <X className="w-6 h-6" />
            </button>
            <div className="glass-card rounded-xl overflow-hidden">
              <div className="relative bg-black">
                <video
                  ref={videoRef}
                  src={fileUrl}
                  className="w-full max-h-[70vh]"
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onEnded={() => setIsPlaying(false)}
                  playsInline
                />
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
                  <input
                    type="range"
                    min={0}
                    max={duration || 0}
                    value={currentTime}
                    onChange={handleSeek}
                    className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-accent-primary mb-2"
                  />
                  <div className="flex items-center justify-between text-white">
                    <div className="flex items-center gap-3">
                      <button onClick={togglePlay} className="p-1 hover:text-accent-primary transition-colors">
                        {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                      </button>
                      <span className="text-xs text-text-secondary">
                        {formatTime(currentTime)} / {formatTime(duration)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 relative">
                      <div
                        className="relative"
                        onMouseEnter={() => setShowVolumeSlider(true)}
                        onMouseLeave={() => setShowVolumeSlider(false)}
                      >
                        <button onClick={toggleMute} className="p-1 hover:text-accent-primary transition-colors">
                          {isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                        </button>
                        {showVolumeSlider && (
                          <div className="absolute bottom-full right-0 mb-2 p-2 bg-bg-elevated rounded-lg">
                            <input
                              type="range"
                              min={0}
                              max={1}
                              step={0.05}
                              value={isMuted ? 0 : volume}
                              onChange={handleVolumeChange}
                              className="w-20 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-accent-primary"
                              style={{ writingMode: 'vertical-lr', height: '80px', width: '4px' }}
                            />
                          </div>
                        )}
                      </div>
                      <button onClick={toggleFullscreen} className="p-1 hover:text-accent-primary transition-colors">
                        <Maximize className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-4 flex items-center justify-between">
                <div>
                  <h3 className="text-text-primary font-medium">{item.title}</h3>
                  <p className="text-text-secondary text-sm mt-1 capitalize">{item.platform}</p>
                </div>
                {onAddToCollection && (
                  <button
                    onClick={() => onAddToCollection(item)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-tertiary border border-border text-text-secondary hover:text-text-primary text-sm transition-colors"
                    title="Add to Collection"
                  >
                    <FolderPlus className="w-4 h-4" />
                    Add to Collection
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

