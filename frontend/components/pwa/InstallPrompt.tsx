'use client';

import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handler);
    setIsInstalled(window.matchMedia('(display-mode: standalone)').matches);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') setIsInstalled(true);
    setDeferredPrompt(null);
  };

  if (isInstalled || !deferredPrompt) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 z-50">
      <div className="glass-card rounded-xl p-4 flex items-start gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/20 shrink-0">
          <Download className="w-5 h-5 text-accent-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-text-primary text-sm font-medium">Install MediaVault Pro</p>
          <p className="text-text-secondary text-xs mt-0.5">Add to home screen for quick access and offline mode</p>
        </div>
        <button onClick={handleInstall} className="text-xs px-3 py-1.5 rounded-lg bg-accent-primary text-white hover:opacity-90">
          Install
        </button>
      </div>
    </div>
  );
}
