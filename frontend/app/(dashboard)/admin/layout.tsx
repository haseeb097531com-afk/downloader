'use client';

import { ReactNode, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store/auth';
import { useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  CreditCard,
  UserCog,
  FileText,
  Settings,
  ArrowLeft,
  Shield,
  AlertTriangle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const NAV_ITEMS = [
  { href: '/admin', label: 'Overview', icon: LayoutDashboard },
  { href: '/admin/tenants', label: 'Tenants', icon: Users },
  { href: '/admin/payments', label: 'Payments', icon: CreditCard },
  { href: '/admin/users', label: 'Users', icon: UserCog },
  { href: '/admin/audit', label: 'Audit', icon: FileText },
  { href: '/admin/settings', label: 'Settings', icon: Settings },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, accessToken, isAuthenticated } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showImpersonationBanner, setShowImpersonationBanner] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_super_admin) {
      router.push('/');
    }
  }, [isAuthenticated, user, router]);

  useEffect(() => {
    if (user?.is_super_admin && user.tenant_id) {
      setShowImpersonationBanner(true);
    }
  }, [user]);

  const stopImpersonating = () => {
    // Clear the X-Tenant-Id header by navigating to admin root
    router.push('/admin');
    setShowImpersonationBanner(false);
  };

  if (!isAuthenticated || !user?.is_super_admin) {
    return null; // Guard handles redirect
  }

  const isImpersonating = !!user.tenant_id && showImpersonationBanner;

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      {/* Impersonation Banner */}
      <AnimatePresence mode="wait">
        {isImpersonating && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-accent-secondary/10 border-b border-accent-secondary/30 px-4 py-2"
          >
            <div className="max-w-7xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <AlertTriangle className="w-4 h-4 text-accent-secondary" />
                <span className="text-text-primary">
                  Impersonating tenant: <strong>{user.tenant_id}</strong>
                </span>
              </div>
              <button
                onClick={stopImpersonating}
                className="px-3 py-1 text-sm text-accent-secondary hover:bg-accent-secondary/10 rounded-lg transition-colors"
              >
                Stop Impersonating
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-bg-elevated/80 backdrop-blur-xl sticky top-0 z-40">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="lg:hidden p-2 rounded-lg hover:bg-bg-tertiary/50 transition-colors"
              aria-label="Toggle sidebar"
            >
              <LayoutDashboard className="w-5 h-5 text-text-primary" />
            </button>
            <h1 className="text-lg font-semibold text-text-primary">Admin Panel</h1>
          </div>
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-accent-secondary" />
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">
              Super Admin
            </span>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar */}
          <AnimatePresence mode="wait">
            {isSidebarOpen && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: '100%', opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                className="lg:hidden fixed inset-0 z-50 bg-black/50"
                onClick={() => setIsSidebarOpen(false)}
              />
            )}
          </AnimatePresence>

          <aside
            className={`fixed lg:static inset-y-0 left-0 z-40 w-64 bg-bg-sidebar border-r border-border transition-all duration-300 flex flex-col ${
              isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
            }`}
          >
            <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
              {NAV_ITEMS.map((item) => {
                const isActive = pathname === item.href || (item.href !== '/admin' && pathname.startsWith(item.href));
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-accent-primary/10 text-accent-primary'
                        : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50'
                    }`}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
            <div className="p-3 border-t border-border">
              <Link
                href="/"
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50 transition-colors"
              >
                <ArrowLeft className="w-5 h-5 flex-shrink-0" />
                <span className="truncate">Back to App</span>
              </Link>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto bg-bg-primary p-6 lg:p-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}