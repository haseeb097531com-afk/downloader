'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store/auth';
import {
  FolderHeart, Search as SearchIcon, Users, Settings2,
  Home, FolderOpen, BarChart2, UserPlus, Download, Zap, Shield, Smartphone as RemoteIcon,
  CreditCard, Crown, Lock
} from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { UpgradeModal } from '@/components/billing/UpgradeModal';
import { FEATURE_ACCESS, PLAN_LABELS, isFeatureUnlocked } from '@/lib/constants/feature-access';

const ALL_NAV_ITEMS = [
  { name: 'Home/Download', path: '/', icon: Home, color: '#6C3FC5', roles: ['owner', 'sub_admin', 'user'], feature: 'home' },
  { name: 'Library', path: '/library', icon: FolderOpen, color: '#3D8BF8', roles: ['owner', 'sub_admin', 'user'], feature: 'library' },
  { name: 'Collections', path: '/collections', icon: FolderHeart, color: '#00F5FF', roles: ['owner', 'sub_admin', 'user'], feature: 'collections' },
  { name: 'Search', path: '/search', icon: SearchIcon, color: '#00FF88', roles: ['owner', 'sub_admin', 'user'], feature: 'search' },
  { name: 'Analytics', path: '/analytics', icon: BarChart2, color: '#FF6B9D', roles: ['owner', 'sub_admin', 'user'], feature: 'analytics_basic' },
  { name: 'Profiles', path: '/profiles', icon: UserPlus, color: '#FFA07A', roles: ['owner', 'sub_admin', 'user'], feature: 'profiles' },
  { name: 'Queue', path: '/queue', icon: Download, color: '#00D2FF', roles: ['owner', 'sub_admin', 'user'], feature: 'queue' },
  { name: 'Plugins', path: '/plugins', icon: Zap, color: '#FFD700', roles: ['owner', 'sub_admin', 'user'], feature: 'plugins' },
  { name: 'Safety Center', path: '/safety', icon: Shield, color: '#FF6B6B', roles: ['owner', 'sub_admin', 'user'], feature: 'safety' },
  { name: 'Remote / Devices', path: '/remote', icon: RemoteIcon, color: '#A29BFE', roles: ['owner', 'sub_admin', 'user'], feature: 'remote' },
  { name: 'Team / Billing', path: '/team', icon: CreditCard, color: '#00F5FF', roles: ['owner'], feature: 'team' },
  { name: 'Tenants', path: '/tenants', icon: Crown, color: '#FFD700', roles: ['owner'], feature: 'tenants' },
  { name: 'Users', path: '/users', icon: Users, color: '#74B9FF', roles: ['owner', 'sub_admin'], feature: null },
  { name: 'Settings', path: '/settings', icon: Settings2, color: '#FD79A8', roles: ['owner'], feature: null },
];

const navItemVariants = {
  rest: { x: 0, scale: 1 },
  hover: { x: 4, scale: 1 },
  press: { scale: 0.98 },
};

const iconVariants = {
  rest: { scale: 1, color: '#8B93B8' },
  hover: { scale: 1.12, color: '#6C5CE7' },
};

const indicatorVariants = {
  rest: { scaleY: 0 },
  hover: { scaleY: 1 },
  active: { scaleY: 1 },
};

const glowVariants = {
  rest: { opacity: 0 },
  hover: { opacity: 1 },
  active: { opacity: 1 },
};

const LogoMark = () => (
  <svg viewBox="0 0 32 32" className="w-8 h-8" aria-hidden="true">
    <defs>
      <linearGradient id="mv-gradient" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop stopColor="#6C5CE7" />
        <stop offset="1" stopColor="#00D2FF" />
      </linearGradient>
    </defs>
    <rect x="4" y="8" width="24" height="18" rx="5" fill="url(#mv-gradient)" opacity="0.95" />
    <path d="M10 8V6a6 6 0 0 1 12 0v2" fill="url(#mv-gradient)" opacity="0.9" />
    <circle cx="16" cy="18" r="3.5" fill="#0f172a" opacity="0.85" />
    <circle cx="16" cy="18" r="1.5" fill="#ffffff" opacity="0.95" />
  </svg>
);

export const Sidebar: React.FC = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [upgradeModal, setUpgradeModal] = useState<{ open: boolean; feature: string; neededPlan: string }>({
    open: false,
    feature: '',
    neededPlan: 'starter',
  });
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const userRole = user?.role || 'user';
  const shouldReduceMotion = useReducedMotion();
  const currentPlan = user?.tenant_plan || 'trial';

  const visibleItems = ALL_NAV_ITEMS.filter((item) => item.roles.includes(userRole));

  const transitionConfig = shouldReduceMotion
    ? { duration: 0 }
    : { type: 'spring' as const, stiffness: 300, damping: 25 };

  const colorTransition = shouldReduceMotion
    ? { duration: 0 }
    : { duration: 0.2 };

  const handleItemClick = (item: typeof ALL_NAV_ITEMS[0]) => {
    if (!item.feature) return;
    const needed = FEATURE_ACCESS[item.feature];
    if (needed && needed !== 'all' && !isFeatureUnlocked(item.feature, currentPlan)) {
      setUpgradeModal({ open: true, feature: item.feature, neededPlan: needed });
    }
  };

  return (
    <aside
      className={`glass-sidebar flex flex-col transition-all duration-500 relative overflow-hidden ${
        isCollapsed ? 'w-[80px]' : 'w-[280px]'
      }`}
    >
      {/* Animated particles background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="particle-glow w-32 h-32 bg-accent-primary/30 top-10 -left-10" style={{ animationDelay: '0s' }} />
        <div className="particle-glow w-24 h-24 bg-accent-secondary/30 top-1/3 -right-8" style={{ animationDelay: '2s' }} />
        <div className="particle-glow w-20 h-20 bg-accent-highlight/20 bottom-20 left-10" style={{ animationDelay: '4s' }} />
      </div>

      {/* TOP — Brand / Logo (fixed) */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-border-primary/50 relative z-10 flex-shrink-0">
        <div className="flex items-center gap-2">
          <LogoMark />
          {!isCollapsed && (
            <span className="font-bold text-lg font-heading">
              <span className="gradient-text">MediaVault</span>
              <span className="text-accent-secondary ml-1 text-sm">Pro</span>
            </span>
          )}
        </div>
        <motion.button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-2 rounded-lg hover:bg-bg-tertiary/50 text-text-secondary hover:text-text-primary transition-all z-10"
          whileHover={shouldReduceMotion ? {} : { rotate: 180, color: '#6C5CE7' }}
          transition={colorTransition}
        >
          {isCollapsed ? '→' : '←'}
        </motion.button>
      </div>

      {/* MIDDLE — Nav list (only scrollable region) */}
      <nav className="flex-1 overflow-y-auto min-h-0 py-3 px-2 space-y-1 relative z-10 sidebar-nav">
        {visibleItems.map((item, index) => {
          const isActive = pathname === item.path || (item.path !== '/' && pathname.startsWith(item.path));
          const Icon = item.icon;
          const neededPlan = item.feature ? FEATURE_ACCESS[item.feature as keyof typeof FEATURE_ACCESS] : null;
          const isLocked = neededPlan && neededPlan !== 'all' && !isFeatureUnlocked(item.feature as string, currentPlan);
          return (
            <motion.div
              key={item.path}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={
                shouldReduceMotion
                  ? { duration: 0 }
                  : { delay: index * 0.04, duration: 0.3, ease: 'easeOut' }
              }
            >
              {isLocked ? (
                <motion.button
                  onClick={() => handleItemClick(item)}
                  className={`relative flex items-center gap-3 rounded-xl cursor-pointer w-full text-left ${
                    isCollapsed ? 'px-2 py-2 justify-center' : 'px-3 py-2.5'
                  }`}
                  initial="rest"
                  whileHover="hover"
                  whileTap="press"
                  animate="rest"
                  variants={shouldReduceMotion ? {
                    rest: {},
                    hover: {},
                    press: {},
                    active: {},
                  } : navItemVariants}
                  transition={transitionConfig}
                >
                  <motion.div
                    className="absolute inset-0 rounded-xl pointer-events-none"
                    style={{
                      background: 'linear-gradient(135deg, #6C3FC5 0%, #3D8BF8 100%)',
                    }}
                    variants={shouldReduceMotion ? { rest: { opacity: 0 }, hover: { opacity: 0.08 } } : glowVariants}
                    transition={colorTransition}
                  />
                  <motion.div
                    className="relative rounded-lg flex-shrink-0"
                    variants={shouldReduceMotion ? { rest: {}, hover: {} } : iconVariants}
                    transition={colorTransition}
                  >
                    <Icon className={isCollapsed ? 'w-9 h-9' : 'w-5 h-5'} style={{ color: item.color }} />
                  </motion.div>
                  {!isCollapsed && (
                    <motion.span
                      className="font-medium text-sm relative z-10"
                      style={{ color: '#8B93B8' }}
                      variants={shouldReduceMotion ? { rest: {}, hover: {} } : { rest: { color: '#8B93B8' }, hover: { color: '#E8EAFF' } }}
                      transition={colorTransition}
                    >
                      {item.name}
                    </motion.span>
                  )}
                  {!isCollapsed && (
                    <span className="ml-auto flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-bg-tertiary/80 text-text-muted text-[10px] font-semibold uppercase tracking-wide">
                      <Lock className="w-3 h-3" />
                      {PLAN_LABELS[neededPlan] || neededPlan}
                    </span>
                  )}
                </motion.button>
              ) : (
                <Link href={item.path}>
                  <motion.div
                    className={`relative flex items-center gap-3 rounded-xl cursor-pointer ${
                      isCollapsed ? 'px-2 py-2 justify-center' : 'px-3 py-2.5'
                    }`}
                    style={{
                      color: isActive ? '#E8EAFF' : undefined,
                    }}
                    initial="rest"
                    whileHover="hover"
                    whileTap="press"
                    animate={isActive ? 'active' : 'rest'}
                    variants={shouldReduceMotion ? {
                      rest: {},
                      hover: {},
                      press: {},
                      active: {},
                    } : navItemVariants}
                    transition={transitionConfig}
                  >
                    {/* Hover/active glow background */}
                    {!isActive && (
                      <motion.div
                        className="absolute inset-0 rounded-xl pointer-events-none"
                        style={{
                          background: 'linear-gradient(135deg, #6C3FC5 0%, #3D8BF8 100%)',
                        }}
                        variants={shouldReduceMotion ? { rest: { opacity: 0 }, hover: { opacity: 0.1 } } : glowVariants}
                        transition={colorTransition}
                      />
                    )}
                    {isActive && (
                      <div
                        className="absolute inset-0 rounded-xl pointer-events-none"
                        style={{
                          background: 'linear-gradient(135deg, #6C3FC5 0%, #3D8BF8 100%)',
                          opacity: 0.14,
                        }}
                      />
                    )}

                    {/* Left indicator bar */}
                    <motion.div
                      className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full origin-center"
                      style={{
                        background: 'linear-gradient(180deg, #6C3FC5 0%, #00D2FF 100%)',
                      }}
                      variants={shouldReduceMotion ? { rest: { scaleY: 0 }, hover: { scaleY: 1 }, active: { scaleY: 1 } } : indicatorVariants}
                      transition={transitionConfig}
                    />

                    {/* Icon wrapper */}
                    <motion.div
                      className="relative rounded-lg flex-shrink-0"
                      style={{
                        backgroundColor: isActive ? 'rgba(255,255,255,0.1)' : undefined,
                      }}
                      variants={shouldReduceMotion ? { rest: {}, hover: {} } : iconVariants}
                      transition={transitionConfig}
                    >
                      <Icon
                        className={isCollapsed ? 'w-9 h-9' : 'w-5 h-5'}
                        style={{ color: isActive ? item.color : undefined }}
                      />
                    </motion.div>

                    {/* Label / tooltip in collapsed mode */}
                    {!isCollapsed ? (
                      <motion.span
                        className="font-medium text-sm relative z-10"
                        style={{ color: isActive ? '#E8EAFF' : '#8B93B8' }}
                        variants={shouldReduceMotion ? { rest: {}, hover: {} } : { rest: { color: '#8B93B8' }, hover: { color: '#E8EAFF' } }}
                        transition={colorTransition}
                      >
                        {item.name}
                      </motion.span>
                    ) : (
                      <span className="sr-only">{item.name}</span>
                    )}

                    {/* Active dot */}
                    {isActive && !isCollapsed && (
                      <motion.div
                        layoutId="active-glow"
                        className="absolute right-2 w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: item.color, boxShadow: `0 0 8px ${item.color}` }}
                      />
                    )}
                  </motion.div>
                </Link>
              )}
            </motion.div>
          );
        })}
      </nav>

      {/* Unlock everything CTA */}
      {!isCollapsed && (
        <div className="px-3 pb-2 relative z-10 flex-shrink-0">
          <button
            onClick={() => setUpgradeModal({ open: true, feature: 'unlock_all', neededPlan: 'starter' })}
            className="w-full py-2 rounded-xl text-xs font-semibold text-text-primary border border-border-primary/60 bg-bg-tertiary/40 hover:bg-bg-tertiary/80 transition-colors"
            style={{
              background: 'linear-gradient(135deg, rgba(108,63,197,0.15) 0%, rgba(61,139,248,0.15) 100%)',
            }}
          >
            Unlock everything
          </button>
        </div>
      )}

      {/* BOTTOM — User + Storage card (fixed) */}
      <div className="p-3 border-t border-border-primary/50 relative z-10 flex-shrink-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-3"
        >
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary flex items-center justify-center text-white font-bold text-sm">
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-status-success rounded-full border-2 border-bg-sidebar" />
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {user?.username || 'User'}
                </p>
                <p className="text-xs text-text-muted truncate">
                  {userRole === 'owner' ? 'Admin' : userRole === 'sub_admin' ? 'Manager' : 'User'}
                </p>
              </div>
            )}
          </div>
          {!isCollapsed && (
            <div className="mt-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-text-secondary">Storage</span>
                <span className="text-xs text-text-muted">75%</span>
              </div>
              <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary"
                  initial={{ width: 0 }}
                  animate={{ width: '75%' }}
                  transition={{ duration: 1, delay: 0.5 }}
                />
              </div>
            </div>
          )}
        </motion.div>
      </div>

      <UpgradeModal
        isOpen={upgradeModal.open}
        onClose={() => setUpgradeModal((prev) => ({ ...prev, open: false }))}
        featureKey={upgradeModal.feature}
        neededPlan={upgradeModal.neededPlan}
      />
    </aside>
  );
};
