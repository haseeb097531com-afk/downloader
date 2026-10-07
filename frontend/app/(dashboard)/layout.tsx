'use client';

import { ReactNode, useEffect } from 'react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { ClipboardModal } from '@/components/desktop/ClipboardModal';
import { StorageAlertBanner } from '@/components/shared/StorageAlertBanner';
import { useDesktopStore } from '@/lib/store/desktop';
import { usePushStore } from '@/lib/store/push';
import { InstallPrompt } from '@/components/pwa/InstallPrompt';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const subscribeClipboardWS = useDesktopStore((state) => state.subscribeClipboardWS);
  const registerSW = usePushStore((state) => state.registerSW);

  useEffect(() => {
    const unsubscribe = subscribeClipboardWS();
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [subscribeClipboardWS]);

  useEffect(() => {
    registerSW();
  }, [registerSW]);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-bg-primary">{children}</main>
      </div>
      <ClipboardModal />
      <StorageAlertBanner />
      <InstallPrompt />
    </div>
  );
}

