'use client';

import { useEffect, useState } from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';

export default function OfflinePage() {
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    setIsOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  if (isOnline) {
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="glass-card rounded-2xl p-8 max-w-md w-full text-center">
        <div className="w-16 h-16 rounded-full bg-status-warning/20 flex items-center justify-center mx-auto mb-6">
          <WifiOff className="w-8 h-8 text-status-warning" />
        </div>
        <h1 className="text-2xl font-bold text-text-primary mb-2">You&apos;re offline</h1>
        <p className="text-text-secondary mb-6">
          No internet connection. Some features may be unavailable until you reconnect.
        </p>
        <button
          onClick={() => (typeof window !== 'undefined' ? window.location.reload() : null)}
          className="px-6 py-3 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity inline-flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    </div>
  );
}

