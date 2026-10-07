'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { usePluginsStore } from '@/lib/store/plugins';

interface InstallModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function InstallModal({ isOpen, onClose }: InstallModalProps) {
  const [repoUrl, setRepoUrl] = useState('');
  const [isInstalling, setIsInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [installSuccess, setInstallSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      setRepoUrl('');
      setError(null);
      setInstallSuccess(false);
      setIsInstalling(false);
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const validateUrl = (url: string): string | null => {
    const trimmed = url.trim();
    if (!trimmed) return 'Repository URL is required';
    if (!trimmed.startsWith('https://')) return 'URL must start with https://';
    if (!trimmed.endsWith('.git') && !trimmed.includes('github.com')) {
      return 'URL must end with .git or be a GitHub URL';
    }
    return null;
  };

  const handleInstall = async () => {
    const validationError = validateUrl(repoUrl);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setIsInstalling(true);

    try {
      const store = usePluginsStore.getState();
      await store.installPlugin(repoUrl);
      setInstallSuccess(true);
      pollForPlugin();
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to install plugin';
      setError(message);
      setIsInstalling(false);
    }
  };

  const pollForPlugin = () => {
    const store = usePluginsStore.getState();
    
    pollingRef.current = window.setInterval(async () => {
      try {
        await store.fetchPlugins();
        const pluginName = repoUrl.split('/').pop()?.replace('.git', '') || '';
        const exists = store.user.some((p) => p.name.toLowerCase() === pluginName.toLowerCase());
        if (exists) {
          if (pollingRef.current) {
            window.clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setIsInstalling(false);
          store.addToast('Plugin installed successfully', 'success');
          setTimeout(() => {
            onClose();
          }, 800);
        }
      } catch {
        // Ignore polling errors
      }
    }, 2000);

    setTimeout(() => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setIsInstalling(false);
      store.addToast('Installation started. Plugin may take a moment to appear.', 'info');
      setTimeout(() => onClose(), 1000);
    }, 30000);
  };

  const handleClose = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={handleClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 20 }}
            className="glass-card w-full max-w-lg rounded-2xl border border-white/10 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-accent-primary/20">
                  <Download className="w-5 h-5 text-accent-primary" />
                </div>
                <div>
                  <h2 className="text-text-primary text-lg font-semibold">Install Plugin</h2>
                  <p className="text-text-secondary text-sm">Install a community plugin from a Git repository</p>
                </div>
              </div>
              <button
                onClick={handleClose}
                disabled={isInstalling}
                className="p-2 rounded-lg hover:bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-4">
              {/* Warning */}
              <div className="flex items-start gap-3 p-4 rounded-lg bg-status-warning/10 border border-status-warning/20">
                <AlertTriangle className="w-5 h-5 text-status-warning flex-shrink-0 mt-0.5" />
                <p className="text-text-secondary text-sm">
                  Only install plugins from trusted sources. Community plugins are not verified by the MediaVault Pro team.
                </p>
              </div>

              {/* Input */}
              <div>
                <label className="block text-text-primary text-sm font-medium mb-2">
                  Git Repository URL
                </label>
                <input
                  ref={inputRef}
                  type="text"
                  value={repoUrl}
                  onChange={(e) => {
                    setRepoUrl(e.target.value);
                    setError(null);
                  }}
                  placeholder="https://github.com/user/plugin.git"
                  disabled={isInstalling}
                  className={`w-full px-4 py-3 rounded-lg bg-bg-tertiary border text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 transition-colors disabled:opacity-50 ${
                    error ? 'border-status-error focus:ring-status-error' : 'border-border focus:ring-accent-primary'
                  }`}
                />
                {error && (
                  <motion.p
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-status-error text-xs mt-2"
                  >
                    {error}
                  </motion.p>
                )}
              </div>

              {/* Loading / Success state */}
              {isInstalling && (
                <div className="flex items-center gap-3 p-4 rounded-lg bg-accent-primary/10">
                  <Loader2 className="w-5 h-5 text-accent-primary animate-spin" />
                  <div>
                    <p className="text-text-primary text-sm font-medium">Cloning & installing...</p>
                    <p className="text-text-secondary text-xs">This may take a minute</p>
                  </div>
                </div>
              )}

              {installSuccess && !isInstalling && (
                <div className="flex items-center gap-3 p-4 rounded-lg bg-status-success/10">
                  <CheckCircle2 className="w-5 h-5 text-status-success" />
                  <div>
                    <p className="text-text-primary text-sm font-medium">Installation complete</p>
                    <p className="text-text-secondary text-xs">Plugin is being loaded</p>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-border">
              <button
                onClick={handleClose}
                disabled={isInstalling}
                className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleInstall}
                disabled={isInstalling || !repoUrl.trim()}
                className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
              >
                {isInstalling ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Installing...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    Install
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
