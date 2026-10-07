'use client';

import { useEffect, useState } from 'react';
import { usePluginsStore } from '@/lib/store/plugins';
import { PluginInfo } from '@/lib/api/plugins';
import InstallModal from '@/components/plugins/InstallModal';
import { FeatureGuard } from '@/components/feature/FeatureGuard';
import {
  Zap,
  Download,
  RefreshCw,
  Power,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ExternalLink,
  GitBranch,
} from 'lucide-react';
import { motion } from 'framer-motion';

const PLATFORM_COLORS: Record<string, string> = {
  youtube: '#FF0000',
  tiktok: '#00F2EA',
  instagram: '#E4405F',
  facebook: '#1877F2',
  twitter: '#1DA1F2',
  whatsapp: '#25D366',
  core: '#6C5CE7',
  community: '#00D2FF',
};

function getStatusBadge(status: string) {
  if (status === 'active') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-status-success/20 text-status-success">
        <CheckCircle2 className="w-3 h-3" />
        Active
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-status-error/20 text-status-error">
      <XCircle className="w-3 h-3" />
      Disabled
    </span>
  );
}

function getPlatformDot(platform: string) {
  const color = PLATFORM_COLORS[platform.toLowerCase()] || '#A29BFE';
  return (
    <span
      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
      style={{ backgroundColor: color }}
      title={platform}
    />
  );
}

function PluginCard({ plugin, section, onUninstall, onToggle }: {
  plugin: PluginInfo;
  section: 'core' | 'user';
  onUninstall?: (name: string) => void;
  onToggle?: (name: string) => void;
}) {
  const [confirmUninstall, setConfirmUninstall] = useState(false);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl p-5 hover:border-accent-primary/30 transition-colors"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4 min-w-0">
          {/* Icon */}
          <div className="w-10 h-10 rounded-lg bg-bg-tertiary flex items-center justify-center flex-shrink-0">
            <Zap className="w-5 h-5 text-accent-primary" />
          </div>

          {/* Info */}
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-text-primary font-semibold truncate">{plugin.name}</h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-bg-tertiary text-text-secondary border border-border">
                {plugin.version}
              </span>
            </div>
            <div className="flex items-center gap-3 text-sm text-text-secondary">
              <span className="truncate">{plugin.author}</span>
              <span className="flex items-center gap-1.5">
                {getPlatformDot(plugin.platform)}
                <span className="capitalize">{plugin.platform}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Right side: status + actions */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {getStatusBadge(plugin.status)}
          {section === 'user' && (
            <div className="flex items-center gap-1">
              {onToggle && (
                <button
                  onClick={() => onToggle(plugin.name)}
                  title={plugin.status === 'active' ? 'Disable' : 'Enable'}
                  className={`p-2 rounded-lg transition-colors ${
                    plugin.status === 'active'
                      ? 'bg-status-success/20 text-status-success hover:bg-status-success hover:text-white'
                      : 'bg-bg-tertiary text-text-muted hover:text-text-primary'
                  }`}
                >
                  <Power className="w-4 h-4" />
                </button>
              )}
              {onUninstall && (
                <>
                  {!confirmUninstall ? (
                    <button
                      onClick={() => setConfirmUninstall(true)}
                      title="Uninstall"
                      className="p-2 rounded-lg bg-status-error/20 text-status-error hover:bg-status-error hover:text-white transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="flex items-center gap-1"
                    >
                      <span className="text-xs text-text-secondary whitespace-nowrap">Remove?</span>
                      <button
                        onClick={() => {
                          onUninstall(plugin.name);
                          setConfirmUninstall(false);
                        }}
                        className="px-2 py-1 rounded text-xs bg-status-error text-white hover:bg-status-error/90"
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setConfirmUninstall(false)}
                        className="px-2 py-1 rounded text-xs bg-bg-tertiary text-text-secondary hover:text-text-primary"
                      >
                        No
                      </button>
                    </motion.div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default function PluginsPage() {
  const {
    core,
    user,
    isLoading,
    isInstalling,
    isReloading,
    fetchPlugins,
    uninstallPlugin,
    reloadPlugins,
    togglePlugin,
    toasts,
    dismissToast,
  } = usePluginsStore();

  const [showInstallModal, setShowInstallModal] = useState(false);

  useEffect(() => {
    fetchPlugins();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <FeatureGuard featureKey="plugins">
      <div className="max-w-6xl mx-auto p-8">
      {/* Toasts */}
      {toasts.map((toast) => (
        <motion.div
          key={toast.id}
          initial={{ opacity: 0, y: -20, x: '-50%' }}
          animate={{ opacity: 1, y: 0, x: '-50%' }}
          exit={{ opacity: 0, y: -20, x: '-50%' }}
          className={`fixed top-4 left-1/2 z-50 px-6 py-3 rounded-lg shadow-lg flex items-center gap-2 ${
            toast.type === 'success'
              ? 'bg-status-success'
              : toast.type === 'error'
              ? 'bg-status-error'
              : 'bg-status-info'
          } text-white`}
        >
          {toast.type === 'success' && <CheckCircle2 className="w-4 h-4" />}
          {toast.type === 'error' && <AlertTriangle className="w-4 h-4" />}
          {toast.type === 'info' && <ExternalLink className="w-4 h-4" />}
          {toast.message}
          <button onClick={() => dismissToast(toast.id)} className="ml-2 hover:opacity-80">
            ✕
          </button>
        </motion.div>
      ))}

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Plugins</h1>
          <p className="text-text-secondary">
            Manage core platforms and community extensions
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={reloadPlugins}
            disabled={isReloading}
            className="px-4 py-2.5 rounded-lg bg-bg-tertiary border border-border text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isReloading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Hot Reload
          </button>
          <button
            onClick={() => setShowInstallModal(true)}
            disabled={isInstalling}
            className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Install Plugin
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="glass-card rounded-xl p-6 animate-pulse">
              <div className="h-5 bg-bg-tertiary rounded w-1/3 mb-4" />
              <div className="h-4 bg-bg-tertiary rounded w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {/* Core Platforms Section */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-5 h-5 text-accent-primary" />
              <h2 className="text-text-primary text-xl font-semibold">Core Platforms</h2>
              <span className="px-2 py-0.5 rounded-full text-xs bg-bg-tertiary text-text-secondary border border-border">
                {core.length}
              </span>
            </div>
            {core.length === 0 ? (
              <div className="glass-card rounded-xl p-8 text-center">
                <Zap className="w-12 h-12 text-text-muted mx-auto mb-3" />
                <p className="text-text-secondary">No core platforms loaded</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {core.map((plugin) => (
                  <PluginCard key={plugin.name} plugin={plugin} section="core" />
                ))}
              </div>
            )}
          </section>

          {/* Community Plugins Section */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <GitBranch className="w-5 h-5 text-accent-secondary" />
              <h2 className="text-text-primary text-xl font-semibold">Community Plugins</h2>
              <span className="px-2 py-0.5 rounded-full text-xs bg-bg-tertiary text-text-secondary border border-border">
                {user.length}
              </span>
            </div>
            {user.length === 0 ? (
              <div className="glass-card rounded-xl p-8 text-center">
                <Download className="w-12 h-12 text-text-muted mx-auto mb-3" />
                <p className="text-text-secondary mb-4">No community plugins installed yet</p>
                <button
                  onClick={() => setShowInstallModal(true)}
                  className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity"
                >
                  Install Your First Plugin
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {user.map((plugin) => (
                  <PluginCard
                    key={plugin.name}
                    plugin={plugin}
                    section="user"
                    onUninstall={uninstallPlugin}
                    onToggle={togglePlugin}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Install Modal */}
      <InstallModal isOpen={showInstallModal} onClose={() => setShowInstallModal(false)} />
      </div>
    </FeatureGuard>
  );
}

