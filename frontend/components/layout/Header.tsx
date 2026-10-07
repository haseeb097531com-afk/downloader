'use client';
import React, { useEffect, useState } from 'react';
import { useTheme } from './ThemeProvider';
import { Wifi, Bell, Smartphone, Search, Moon, Sun } from 'lucide-react';
import { useDesktopStore } from '@/lib/store/desktop';
import { useRouter } from 'next/navigation';
import { NetworkWidget } from '@/components/scheduler/NetworkWidget';
import { getSystemSpeed, SystemSpeed } from '@/lib/api/system';
import { usePushStore } from '@/lib/store/push';
import { useAuthStore } from '@/lib/store/auth';
import { motion } from 'framer-motion';

export const Header: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();
  const { status } = useDesktopStore();
  const [speed, setSpeed] = useState<SystemSpeed | null>(null);
  const [isOnline, setIsOnline] = useState(true);
  const user = useAuthStore((state) => state.user);
  const isOwner = user?.role === 'owner';

  const clipboardRunning = status?.clipboard_running;

  useEffect(() => {
    let cancelled = false;
    const fetchSpeed = async () => {
      try {
        const data = await getSystemSpeed();
        if (!cancelled) setSpeed(data);
      } catch (e) {
        console.error(e);
      }
    };
    fetchSpeed();
    const interval = setInterval(fetchSpeed, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    setIsOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const displayMbPerSec = speed ? (speed.current_speed_mbps / 8).toFixed(1) : '0.0';
  const isActive = speed ? speed.turbo_mode && speed.current_speed_mbps > 0 : false;

  return (
    <header className="h-16 flex items-center justify-between px-6 border-b border-border bg-bg-elevated/80 backdrop-blur-xl sticky top-0 z-40 relative">
      {/* Search Bar */}
      <div className="flex items-center gap-4 flex-1 max-w-2xl">
        <div className="relative w-full group">
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-accent-highlight transition-colors">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            placeholder="Search media, profiles, tags..."
            className="w-full glass-input pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-highlight/50 focus:shadow-[0_0_20px_rgba(0,245,255,0.1)]"
          />
        </div>
      </div>

      {/* Right side controls */}
      <div className="flex items-center gap-3">
        {/* Online/Offline Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-bg-tertiary/30">
          <div className="relative">
            <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-status-success' : 'bg-status-error'}`} />
            {isOnline && (
              <div className="absolute inset-0 w-2 h-2 rounded-full bg-status-success animate-ping opacity-75" />
            )}
          </div>
          <span className="text-xs font-medium text-text-secondary">
            {isOnline ? 'Online' : 'Offline'}
          </span>
        </div>

        {/* Speed Indicator */}
        {speed && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
              isActive
                ? 'border-accent-secondary/30 bg-accent-secondary/10 text-accent-secondary'
                : 'border-border bg-bg-tertiary/30 text-text-muted'
            }`}
            title={`Active workers: ${speed.active_workers} | Fragments: ${speed.concurrent_fragments} | aria2: ${speed.aria2_available ? 'installed' : 'not installed'}`}
          >
            <Wifi className={`w-4 h-4 ${isActive ? 'animate-pulse' : ''}`} />
            <span className="text-sm font-medium font-mono">{displayMbPerSec} MB/s</span>
          </motion.div>
        )}

        {/* Network Widget */}
        <NetworkWidget compact />

        {/* Clipboard */}
        {isOwner && (
          <button
            onClick={() => router.push('/settings')}
            className={`p-2 rounded-lg transition-all relative ${
              clipboardRunning ? 'text-accent-secondary bg-accent-secondary/10' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary/50'
            }`}
            title={clipboardRunning ? 'Clipboard monitor active' : 'Clipboard monitor off'}
          >
            <Bell className={`w-5 h-5 ${clipboardRunning ? 'animate-pulse' : ''}`} />
            {clipboardRunning && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-accent-secondary animate-pulse" />
            )}
          </button>
        )}

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-bg-tertiary/50 transition-all text-text-muted hover:text-text-primary relative overflow-hidden group"
        >
          <motion.div
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            {theme === 'dark' ? (
              <Sun className="w-5 h-5 text-accent-secondary" />
            ) : (
              <Moon className="w-5 h-5 text-accent-primary" />
            )}
          </motion.div>
        </button>

        {/* Push Bell */}
        <PushBell />

        {/* Remote Control */}
        <button
          onClick={() => router.push('/remote-control')}
          className="p-2 rounded-lg hover:bg-bg-tertiary/50 transition-all text-text-muted hover:text-text-primary"
          title="Open Remote Control"
        >
          <Smartphone className="w-5 h-5" />
        </button>

        {/* User Avatar */}
        <div className="relative">
          <div
            className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary cursor-pointer border-2 border-border hover:border-accent-highlight transition-all shadow-lg shadow-accent-primary/20"
            onClick={() => router.push('/settings')}
          />
          <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-status-success rounded-full border-2 border-bg-elevated" />
        </div>
      </div>
    </header>
  );
};

function PushBell() {
  const { permission, isSubscribed } = usePushStore();
  const router = useRouter();
  const isActive = permission === 'granted' && isSubscribed;

  return (
    <button
      onClick={() => router.push('/settings#notifications-pwa')}
      className={`p-2 rounded-lg transition-all relative ${
        isActive ? 'text-accent-secondary bg-accent-secondary/10' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary/50'
      }`}
      title={isActive ? 'Push notifications active' : 'Push notifications off'}
    >
      <Bell className={`w-5 h-5 ${isActive ? 'animate-pulse' : ''}`} />
      {isActive && (
        <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-accent-secondary animate-pulse" />
      )}
    </button>
  );
}

