'use client';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download, Wand2, CalendarClock, ListPlus, Pause, X,
  CheckCircle2, AlertCircle, Zap, HardDrive, Activity,
  Music2, Film, FileDown, Clock, Star, Trash2,
  MonitorPlay, Gauge, ArrowDownToLine, Video
} from 'lucide-react';
import { isProfileUrl, getPlatformFromUrl } from '@/lib/utils/url';
import { ProfileScrapeModal } from '@/components/profiles/ProfileScrapeModal';
import { TrimmerModal } from '@/components/media/TrimmerModal';
import DuplicateModal from '@/components/media/DuplicateModal';
import ScheduleModal from '@/components/scheduler/ScheduleModal';
import { BulkImportModal } from '@/components/bulk/BulkImportModal';
import { createDownload, DuplicateError } from '@/lib/api/downloads';
import { useDedupStore } from '@/lib/store/dedup';
import { DuplicateMatch } from '@/lib/api/dedup';

// Sample data for recent downloads
const RECENT_DOWNLOADS = [
  { id: '1', title: 'Amazing Nature Documentary - 4K', platform: 'youtube', size: '1.2 GB', status: 'done', thumbnail: null, duration: '12:34' },
  { id: '2', title: 'TikTok Viral Dance Compilation', platform: 'tiktok', size: '456 MB', status: 'downloading', thumbnail: null, duration: '3:21' },
  { id: '3', title: 'Instagram Reels - Travel Vlog', platform: 'instagram', size: '234 MB', status: 'done', thumbnail: null, duration: '1:45' },
  { id: '4', title: 'Twitter Video - Tech Review', platform: 'twitter', size: '89 MB', status: 'queue', thumbnail: null, duration: '5:12' },
  { id: '5', title: 'YouTube Music - Top Hits 2024', platform: 'youtube', size: '678 MB', status: 'done', thumbnail: null, duration: '45:00' },
];

// Sample queue items
const SAMPLE_QUEUE = [
  { id: 'q1', title: 'Advanced React Patterns Tutorial', platform: 'youtube', progress: 67, speed: '2.4 MB/s', eta: '2m 15s', status: 'downloading' },
  { id: 'q2', title: 'Viral TikTok Trends October', platform: 'tiktok', progress: 34, speed: '1.8 MB/s', eta: '4m 32s', status: 'downloading' },
  { id: 'q3', title: 'Instagram Story Highlights', platform: 'instagram', progress: 0, speed: null, eta: null, status: 'queue' },
];

const PLATFORM_ICONS: Record<string, { icon: React.ElementType; color: string; glow: string }> = {
  youtube: { icon: Video, color: '#FF0000', glow: 'rgba(255, 0, 0, 0.3)' },
  tiktok: { icon: Music2, color: '#00F2EA', glow: 'rgba(0, 242, 234, 0.3)' },
  instagram: { icon: Film, color: '#E4405F', glow: 'rgba(228, 64, 95, 0.3)' },
  twitter: { icon: Video, color: '#1DA1F2', glow: 'rgba(29, 161, 242, 0.3)' },
};

const STATS_DATA = [
  { label: 'Total Downloads', value: '1,247', change: '+12%', icon: ArrowDownToLine, color: '#6C3FC5', glow: 'rgba(108, 63, 197, 0.3)' },
  { label: 'Active Queue', value: '3', change: '-2', icon: Activity, color: '#3D8BF8', glow: 'rgba(61, 139, 248, 0.3)' },
  { label: 'Storage Used', value: '84.2 GB', change: '+5%', icon: HardDrive, color: '#00F5FF', glow: 'rgba(0, 245, 255, 0.3)' },
  { label: 'Speed', value: '12.4 MB/s', change: 'Turbo', icon: Gauge, color: '#00FF88', glow: 'rgba(0, 255, 136, 0.3)' },
];

export default function HomePage() {
  const [url, setUrl] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [showTrimmer, setShowTrimmer] = useState(false);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [duplicateMatches, setDuplicateMatches] = useState<DuplicateMatch[] | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState('mp4');
  const [selectedQuality, setSelectedQuality] = useState('best');
  const [turboEnabled, setTurboEnabled] = useState(true);
  const { checkUrl } = useDedupStore();

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text');
    if (isProfileUrl(pasted)) {
      setShowModal(true);
    }
  };

  const handleDownload = async () => {
    if (!url.trim()) return;
    if (isProfileUrl(url)) {
      setShowModal(true);
      return;
    }
    try {
      await createDownload({ url });
    } catch (e) {
      if (e instanceof DuplicateError && e.matches) {
        setDuplicateMatches(e.matches);
        return;
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedUrl = e.dataTransfer.getData('text/plain');
    if (droppedUrl) {
      setUrl(droppedUrl);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const checkForDuplicates = async () => {
      if (!url || isProfileUrl(url)) {
        setDuplicateMatches(null);
        return;
      }
      const trimmed = url.trim();
      if (!trimmed) return;
      try {
        const matches = await checkUrl(trimmed);
        if (!cancelled && matches && matches.length > 0) {
          setDuplicateMatches(matches);
        } else if (!cancelled) {
          setDuplicateMatches(null);
        }
      } catch {
        // silent dedup check failure
      }
    };

    const timer = setTimeout(checkForDuplicates, 800);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [url, checkUrl]);

  const isProfile = isProfileUrl(url);
  const platform = getPlatformFromUrl(url);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
        delayChildren: 0.1,
      },
    },
  };

  return (
    <div className="min-h-screen relative">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="hero-backdrop relative overflow-hidden"
      >
        <div className="hero-glow" aria-hidden="true" />
        <div className="relative z-10 max-w-7xl mx-auto px-6 py-12">
          {/* Logo & Title */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-10"
          >
            <div className="inline-flex items-center gap-3 mb-4">
              <div className="relative w-12 h-12">
                <div className="absolute inset-0 rounded-xl animated-gradient opacity-80" />
                <div className="absolute inset-0 rounded-xl bg-gradient-to-tr from-accent-primary to-accent-secondary animate-pulse-ring" />
                <Download className="absolute inset-0 m-auto w-6 h-6 text-white" />
              </div>
              <h1 className="text-4xl md:text-5xl font-bold font-heading gradient-text">
                MediaVault Pro
              </h1>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold font-heading text-text-primary mb-3">
              Download <span className="gradient-text">&</span> Organize
            </h2>
            <p className="text-text-secondary text-lg max-w-2xl mx-auto">
              Paste a video or profile URL to get started. Supports YouTube, TikTok, Instagram, Twitter and more.
            </p>
          </motion.div>

          {/* Main Download Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="max-w-4xl mx-auto mb-8"
          >
            <div className="glass-card p-6 md:p-8 relative overflow-hidden">
              {/* Animated border glow */}
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-accent-primary/20 via-accent-secondary/20 to-accent-highlight/20 opacity-0 hover:opacity-100 transition-opacity duration-500" />
              <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent-primary/50 to-transparent" />

              {/* URL Input */}
              <div className="relative mb-6">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted">
                  <Wand2 className="w-5 h-5" />
                </div>
                <input
                  type="text"
                  placeholder="Paste a video or profile URL here..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onPaste={handlePaste}
                  className="w-full h-14 pl-14 pr-32 rounded-xl text-base outline-none transition-all duration-300 glass-input text-text-primary placeholder:text-text-muted"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
                  <button
                    onClick={() => setShowScheduleModal(true)}
                    className="p-2.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-tertiary/50 transition-all"
                    title="Schedule download"
                  >
                    <CalendarClock className="w-5 h-5" />
                  </button>
                  <button
                    onClick={handleDownload}
                    disabled={!url}
                    className="glow-button relative h-10 px-6 rounded-xl text-sm font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed overflow-hidden"
                  >
                    <span className="relative z-10 flex items-center gap-2">
                      {isProfile ? 'Scrape' : 'Download'}
                      <ArrowDownToLine className="w-4 h-4" />
                    </span>
                  </button>
                </div>
              </div>

              {/* Duplicate warning */}
              <AnimatePresence>
                {duplicateMatches && duplicateMatches.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="flex items-center gap-2 px-4 py-3 rounded-xl bg-status-warning/10 border border-status-warning/20 mb-6"
                  >
                    <AlertCircle className="w-5 h-5 text-status-warning" />
                    <span className="text-text-secondary text-sm">
                      Already in library ({duplicateMatches[0].similarity}% match)
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Profile hint */}
              {isProfile && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm text-accent-primary font-medium mb-4 flex items-center gap-2"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Profile URL detected — ready to scrape {platform}
                </motion.p>
              )}

              {/* Format / Quality / Turbo Toggle Cards */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <motion.div
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setSelectedFormat(selectedFormat === 'mp4' ? 'mp3' : 'mp4')}
                  className={`toggle-card glass-card p-4 rounded-xl cursor-pointer ${selectedFormat === 'mp4' ? 'active' : ''}`}
                >
                  <div className="relative z-10 flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${selectedFormat === 'mp4' ? 'bg-accent-primary/20 text-accent-primary' : 'bg-bg-tertiary text-text-muted'}`}>
                      <Film className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs text-text-muted uppercase tracking-wide">Format</p>
                      <p className="text-sm font-semibold text-text-primary uppercase">{selectedFormat}</p>
                    </div>
                  </div>
                </motion.div>

                <motion.div
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setSelectedQuality(selectedQuality === 'best' ? '4320p' : selectedQuality === '4320p' ? '2160p' : selectedQuality === '2160p' ? '1440p' : selectedQuality === '1440p' ? '1080p' : selectedQuality === '1080p' ? '720p' : selectedQuality === '720p' ? '480p' : selectedQuality === '480p' ? 'audio_only' : 'best')}
                  className={`toggle-card glass-card p-4 rounded-xl cursor-pointer ${selectedQuality !== 'best' ? 'active' : ''}`}
                >
                  <div className="relative z-10 flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${selectedQuality !== 'best' ? 'bg-accent-secondary/20 text-accent-secondary' : 'bg-bg-tertiary text-text-muted'}`}>
                      <MonitorPlay className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs text-text-muted uppercase tracking-wide">Quality</p>
                      <p className="text-sm font-semibold text-text-primary">{selectedQuality}</p>
                    </div>
                  </div>
                </motion.div>

                <motion.div
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setTurboEnabled(!turboEnabled)}
                  className={`toggle-card glass-card p-4 rounded-xl cursor-pointer ${turboEnabled ? 'active' : ''}`}
                >
                  <div className="relative z-10 flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${turboEnabled ? 'bg-status-success/20 text-status-success' : 'bg-bg-tertiary text-text-muted'}`}>
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs text-text-muted uppercase tracking-wide">Turbo</p>
                      <p className="text-sm font-semibold text-text-primary">{turboEnabled ? 'On' : 'Off'}</p>
                    </div>
                  </div>
                </motion.div>
              </div>

              {/* Quick Actions */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowBulkModal(true)}
                  className="h-10 px-4 rounded-xl text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50 border border-border hover:border-accent-primary/30 transition-all flex items-center gap-2"
                >
                  <ListPlus className="w-4 h-4" />
                  Bulk Import
                </button>
                <button
                  onClick={() => setShowScheduleModal(true)}
                  className="h-10 px-4 rounded-xl text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50 border border-border hover:border-accent-primary/30 transition-all flex items-center gap-2"
                >
                  <CalendarClock className="w-4 h-4" />
                  Schedule
                </button>
              </div>
            </div>
          </motion.div>

          {/* Drag & Drop Zone */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`max-w-4xl mx-auto mb-12 drag-zone rounded-2xl p-8 text-center cursor-pointer transition-all ${
              isDragOver ? 'drag-active' : ''
            }`}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <input id="file-input" type="file" multiple className="hidden" />
            <motion.div
              animate={{ y: isDragOver ? -5 : 0 }}
              className="flex flex-col items-center gap-4"
            >
              <div className={`p-4 rounded-2xl transition-all ${isDragOver ? 'bg-accent-highlight/10 scale-110' : 'bg-bg-tertiary/50'}`}>
                <FileDown className={`w-8 h-8 transition-colors ${isDragOver ? 'text-accent-highlight' : 'text-text-muted'}`} />
              </div>
              <div>
                <p className="text-text-primary font-medium mb-1">
                  {isDragOver ? 'Drop URLs here' : 'Drag & drop URLs for bulk import'}
                </p>
                <p className="text-text-secondary text-sm">
                  Supports multiple URLs at once
                </p>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </motion.div>

      {/* Stats Dashboard */}
      <div className="max-w-7xl mx-auto px-6 mb-12">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {STATS_DATA.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              whileHover={{ scale: 1.03, y: -4 }}
              className="glass-card p-5 card-hover relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 w-24 h-24 rounded-full blur-[40px] opacity-20 group-hover:opacity-40 transition-opacity"
                style={{ background: stat.color }} />
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-3">
                  <div
                    className="p-2 rounded-lg"
                    style={{ backgroundColor: `${stat.color}20`, color: stat.color }}
                  >
                    <stat.icon className="w-5 h-5" />
                  </div>
                  <span className="text-xs font-medium text-status-success bg-status-success/10 px-2 py-1 rounded-full">
                    {stat.change}
                  </span>
                </div>
                <p className="text-text-secondary text-xs uppercase tracking-wide mb-1">{stat.label}</p>
                <motion.p
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 + 0.3 }}
                  className="text-2xl font-bold font-heading text-text-primary"
                >
                  {stat.value}
                </motion.p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Queue Preview */}
      <div className="max-w-7xl mx-auto px-6 mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="flex items-center justify-between mb-6"
        >
          <div>
            <h3 className="text-2xl font-bold font-heading text-text-primary mb-1">Active Downloads</h3>
            <p className="text-text-secondary text-sm">Currently downloading items</p>
          </div>
          <a href="/queue" className="text-sm text-accent-primary hover:text-accent-secondary transition-colors">
            View All →
          </a>
        </motion.div>

        <div className="space-y-4">
          {SAMPLE_QUEUE.map((item, index) => {
            const PlatformIcon = PLATFORM_ICONS[item.platform]?.icon || Download;
            const platformColor = PLATFORM_ICONS[item.platform]?.color || '#6C3FC5';

            return (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="glass-card p-5 card-hover relative overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-accent-primary to-accent-secondary opacity-60" />
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-xl bg-bg-tertiary/50 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
                    <PlatformIcon className="w-8 h-8" style={{ color: platformColor }} />
                    <div className="absolute inset-0 rounded-xl opacity-20" style={{ boxShadow: `inset 0 0 20px ${platformColor}` }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-text-primary font-medium truncate">{item.title}</h4>
                      <span
                        className="px-2 py-0.5 rounded-full text-xs text-white flex-shrink-0"
                        style={{ backgroundColor: platformColor }}
                      >
                        {item.platform}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-text-secondary mb-3">
                      {item.speed && (
                        <span className="flex items-center gap-1">
                          <Gauge className="w-3.5 h-3.5" />
                          {item.speed}
                        </span>
                      )}
                      {item.eta && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          ETA: {item.eta}
                        </span>
                      )}
                    </div>
                    <div className="relative w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
                      <motion.div
                        className="h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary progress-glow"
                        initial={{ width: 0 }}
                        animate={{ width: `${item.progress}%` }}
                        transition={{ duration: 0.6, delay: index * 0.15 }}
                      />
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-text-muted">{item.progress}%</span>
                      <span className={`text-xs font-medium ${item.status === 'downloading' ? 'text-accent-secondary' : 'text-status-warning'}`}>
                        {item.status === 'downloading' ? 'Downloading' : 'Queued'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button className="p-2 rounded-lg bg-bg-tertiary/50 text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-all">
                      <Pause className="w-4 h-4" />
                    </button>
                    <button className="p-2 rounded-lg bg-status-error/10 text-status-error hover:bg-status-error hover:text-white transition-all">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Recent Downloads */}
      <div className="max-w-7xl mx-auto px-6 mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="flex items-center justify-between mb-6"
        >
          <div>
            <h3 className="text-2xl font-bold font-heading text-text-primary mb-1">Recent Downloads</h3>
            <p className="text-text-secondary text-sm">Your last 5 downloads</p>
          </div>
        </motion.div>

        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Thumbnail</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Title</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Platform</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Size</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Status</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {RECENT_DOWNLOADS.map((item, index) => {
                  const PlatformIcon = PLATFORM_ICONS[item.platform]?.icon || Download;
                  const platformColor = PLATFORM_ICONS[item.platform]?.color || '#6C3FC5';

                  return (
                    <motion.tr
                      key={item.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="hover:bg-bg-tertiary/30 transition-colors group"
                    >
                      <td className="px-6 py-4">
                        <div className="w-16 h-12 rounded-lg bg-bg-tertiary/50 flex items-center justify-center relative overflow-hidden">
                          <PlatformIcon className="w-6 h-6" style={{ color: platformColor }} />
                          <div className="absolute inset-0 rounded-lg opacity-10" style={{ boxShadow: `inset 0 0 15px ${platformColor}` }} />
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="text-text-primary font-medium text-sm truncate max-w-xs">{item.title}</p>
                          <p className="text-text-muted text-xs mt-0.5">{item.duration}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-white"
                          style={{ backgroundColor: platformColor }}
                        >
                          <PlatformIcon className="w-3 h-3" />
                          {item.platform}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-text-secondary text-sm">{item.size}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`status-badge ${
                          item.status === 'done' ? 'status-success' :
                          item.status === 'downloading' ? 'status-downloading' :
                          'status-warning'
                        }`}>
                          {item.status === 'done' ? 'Completed' : item.status === 'downloading' ? 'Downloading' : 'Queued'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button className="p-1.5 rounded-lg hover:bg-bg-tertiary text-text-muted hover:text-text-primary transition-all">
                            <Star className="w-4 h-4" />
                          </button>
                          <button className="p-1.5 rounded-lg hover:bg-bg-tertiary text-text-muted hover:text-text-primary transition-all">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Platform Icons */}
      <div className="max-w-7xl mx-auto px-6 mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="text-center mb-8"
        >
          <h3 className="text-2xl font-bold font-heading text-text-primary mb-2">Supported Platforms</h3>
          <p className="text-text-secondary text-sm">Download from your favorite platforms</p>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {Object.entries(PLATFORM_ICONS).map(([platform, config], index) => {
            const Icon = config.icon;
            return (
              <motion.div
                key={platform}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
                whileHover={{ scale: 1.05, y: -4 }}
                className="glass-card p-4 card-hover flex flex-col items-center justify-center text-center gap-2 cursor-pointer min-w-0"
                style={{ '--glow-color': config.glow } as React.CSSProperties}
              >
                <div
                  className="p-2 rounded-xl relative"
                  style={{ backgroundColor: `${config.color}20`, color: config.color }}
                >
                  <Icon className="w-5 h-5" />
                  <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ boxShadow: `0 0 20px ${config.glow}` }} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text-primary capitalize whitespace-nowrap">{platform}</p>
                  <p className="text-text-muted text-xs">Supported</p>
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      </div>

      {/* Modals */}
      {showModal && <ProfileScrapeModal url={url} onClose={() => setShowModal(false)} />}
      {showTrimmer && <TrimmerModal isOpen={showTrimmer} onClose={() => setShowTrimmer(false)} streamUrl={url} />}
      <DuplicateModal
        isOpen={!!duplicateMatches}
        matches={duplicateMatches}
        url={url}
        onClose={() => setDuplicateMatches(null)}
      />
      <ScheduleModal
        isOpen={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
        profileId=""
      />
      <BulkImportModal isOpen={showBulkModal} onClose={() => setShowBulkModal(false)} />
    </div>
  );
}
