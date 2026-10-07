'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HardDrive, X } from 'lucide-react';
import { getDiskStatus, DiskStatus } from '@/lib/api/system';
import { useRouter } from 'next/navigation';

export function StorageAlertBanner() {
  const [disk, setDisk] = useState<DiskStatus | null>(null);
  const [visible, setVisible] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const fetchDisk = async () => {
      try {
        const data = await getDiskStatus();
        setDisk(data);
        setVisible(data.guard_active);
      } catch (e) {
        console.error(e);
      }
    };

    fetchDisk();
    const interval = setInterval(fetchDisk, 15000);

    return () => clearInterval(interval);
  }, []);

  return (
    <AnimatePresence>
      {visible && disk && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="fixed top-0 left-0 right-0 z-[60]"
        >
          <div className="mx-4 mt-4">
            <div className="glass-card rounded-xl p-4 border-l-4 border-status-warning flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <HardDrive className="w-5 h-5 text-status-warning shrink-0" />
                <p className="text-text-primary text-sm font-medium">
                  Low disk space - new downloads paused
                </p>
                <span className="text-text-secondary text-xs">
                  {disk.free_gb.toFixed(1)} GB free of {disk.total_gb.toFixed(1)} GB
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => router.push('/settings')}
                  className="px-3 py-1.5 rounded-lg bg-status-warning/20 text-status-warning text-xs font-medium hover:bg-status-warning/30 transition-colors"
                >
                  Open Settings
                </button>
                <button
                  onClick={() => setVisible(false)}
                  className="p-1.5 rounded-lg hover:bg-bg-tertiary text-text-muted hover:text-text-primary transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

