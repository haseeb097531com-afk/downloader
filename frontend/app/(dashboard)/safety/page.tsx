'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, ShieldCheck, Lock, Key, Plus, X, RotateCcw, Trash2, AlertTriangle, Gauge } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { useModerationStore } from '@/lib/store/moderation';
import { FeatureGuard } from '@/components/feature/FeatureGuard';

const SENSITIVITY_LABELS = ['Very Low', 'Low', 'Medium', 'High', 'Very High'];

function ShakeAnimation({ children, trigger }: { children: React.ReactNode; trigger: boolean }) {
  return (
    <motion.div
      animate={trigger ? { x: [0, -8, 8, -6, 6, -3, 3, 0] } : { x: 0 }}
      transition={trigger ? { duration: 0.5 } : { duration: 0 }}
    >
      {children}
    </motion.div>
  );
}

export default function SafetyCenterPage() {
  const {
    settings,
    quarantined,
    isLoading,
    isSaving,
    isUnlocked,
    toasts,
    dismissToast,
    fetchSettings,
    updateSettings,
    setPin,
    verifyPin,
    fetchQuarantined,
    restoreItem,
    purgeItem,
    unlock,
    addToast,
  } = useModerationStore();

  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState('');
  const [shake, setShake] = useState(false);
  const [localSafeMode, setLocalSafeMode] = useState(false);
  const [localSensitivity, setLocalSensitivity] = useState(3);
  const [blacklist, setBlacklist] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState('');
  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [pinErrorMsg, setPinErrorMsg] = useState('');
  const [purgeConfirmId, setPurgeConfirmId] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
    fetchQuarantined();
  }, [fetchSettings, fetchQuarantined]);

  useEffect(() => {
    if (settings) {
      setLocalSafeMode(settings.safe_mode_enabled);
      setLocalSensitivity(settings.sensitivity);
      setBlacklist([...settings.blacklist]);
    }
  }, [settings]);

  const handleVerifyPin = useCallback(async () => {
    if (pinInput.length !== 4 || !/^\d{4}$/.test(pinInput)) {
      setPinError('Enter a 4-digit PIN');
      setShake(true);
      setTimeout(() => setShake(false), 500);
      return;
    }
    setPinError('');
    const success = await verifyPin(pinInput);
    if (success) {
      setPinInput('');
    } else {
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
  }, [pinInput, verifyPin]);

  const handleUnlockWithoutPin = useCallback(async () => {
    if (settings?.pin_set) return;
    unlock();
  }, [settings?.pin_set, unlock]);

  const handleSaveSafeMode = useCallback(async () => {
    await updateSettings({
      safe_mode_enabled: localSafeMode,
      sensitivity: localSensitivity,
    });
  }, [localSafeMode, localSensitivity, updateSettings]);

  const handleAddKeyword = useCallback(() => {
    const trimmed = newKeyword.trim().toLowerCase();
    if (!trimmed) return;
    if (blacklist.includes(trimmed)) {
      addToast('Keyword already in blacklist', 'error');
      return;
    }
    const next = [...blacklist, trimmed];
    setBlacklist(next);
    setNewKeyword('');
    updateSettings({ blacklist: next });
  }, [newKeyword, blacklist, updateSettings, addToast]);

  const handleRemoveKeyword = useCallback(
    (word: string) => {
      const next = blacklist.filter((k) => k !== word);
      setBlacklist(next);
      updateSettings({ blacklist: next });
    },
    [blacklist, updateSettings]
  );

  const handleChangePin = useCallback(async () => {
    setPinErrorMsg('');
    if (newPin.length !== 4 || !/^\d{4}$/.test(newPin)) {
      setPinErrorMsg('PIN must be exactly 4 digits');
      return;
    }
    if (newPin !== confirmPin) {
      setPinErrorMsg('PINs do not match');
      return;
    }
    await setPin(newPin);
    setNewPin('');
    setConfirmPin('');
  }, [newPin, confirmPin, setPin]);

  const handleRestore = useCallback(
    async (id: string) => {
      await restoreItem(id);
    },
    [restoreItem]
  );

  const handlePurge = useCallback(
    async (id: string) => {
      setPurgeConfirmId(null);
      await purgeItem(id);
    },
    [purgeItem]
  );

  // PIN Gate
  if (!isUnlocked) {
    return (
      <FeatureGuard featureKey="safety">
        <div className="min-h-[70vh] flex items-center justify-center p-8">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-full bg-accent-primary/20 flex items-center justify-center mx-auto mb-4">
              <Lock className="w-8 h-8 text-accent-primary" />
            </div>
            <h1 className="text-3xl font-bold text-text-primary mb-2">Safety Center</h1>
            <p className="text-text-secondary">
              {settings?.pin_set ? 'Enter your PIN to access safety settings' : 'Set up a PIN to protect safety settings'}
            </p>
          </div>

          <ShakeAnimation trigger={shake}>
            <div className="glass-card rounded-xl p-6 border border-white/5">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">4-Digit PIN</label>
                  <input
                    type="password"
                    inputMode="numeric"
                    maxLength={4}
                    value={pinInput}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, '').slice(0, 4);
                      setPinInput(val);
                      setPinError('');
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleVerifyPin();
                    }}
                    placeholder="••••"
                    className="w-full px-4 py-3 bg-bg-tertiary border border-white/10 rounded-lg text-white text-center text-2xl tracking-[0.5em] placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
                  />
                  {pinError && <p className="text-status-error text-xs mt-2">{pinError}</p>}
                </div>

                {settings?.pin_set ? (
                  <button
                    onClick={handleVerifyPin}
                    className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                  >
                    <Key className="w-4 h-4" />
                    Verify PIN
                  </button>
                ) : (
                  <button
                    onClick={handleVerifyPin}
                    className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                  >
                    <Lock className="w-4 h-4" />
                    Set PIN
                  </button>
                )}

                {!settings?.pin_set && (
                  <button
                    onClick={handleUnlockWithoutPin}
                    className="w-full py-3 px-4 rounded-xl bg-bg-tertiary border border-white/10 text-text-secondary hover:text-text-primary font-medium transition-colors"
                  >
                    Skip for now
                  </button>
                )}
              </div>
            </div>
          </ShakeAnimation>

          <AnimatePresence>
            {toasts.map((toast) => (
              <motion.div
                key={toast.id}
                initial={{ opacity: 0, y: -20, x: '-50%' }}
                animate={{ opacity: 1, y: 0, x: '-50%' }}
                exit={{ opacity: 0, y: -20, x: '-50%' }}
                className={`fixed top-4 left-1/2 z-50 px-6 py-3 rounded-lg shadow-lg ${
                  toast.type === 'success' ? 'bg-status-success' : toast.type === 'error' ? 'bg-status-error' : 'bg-status-info'
                } text-white`}
              >
                {toast.message}
                <button onClick={() => dismissToast(toast.id)} className="ml-3 hover:opacity-80">
                  ×
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </FeatureGuard>
    );
  }

  return (
    <FeatureGuard featureKey="safety">
      <div className="max-w-3xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Safety Center</h1>
        <p className="text-text-secondary">Manage safe mode, content filtering, and quarantined items</p>
      </div>

      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: -20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: -20, x: '-50%' }}
            className={`fixed top-4 left-1/2 z-50 px-6 py-3 rounded-lg shadow-lg ${
              toast.type === 'success' ? 'bg-status-success' : toast.type === 'error' ? 'bg-status-error' : 'bg-status-info'
            } text-white`}
          >
            {toast.message}
            <button onClick={() => dismissToast(toast.id)} className="ml-3 hover:opacity-80">
              ×
            </button>
          </motion.div>
        ))}
      </AnimatePresence>

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
        <div className="space-y-6">
          {/* Safe Mode */}
          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-primary/20">
                <Shield className="w-5 h-5 text-accent-primary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Safe Mode</h2>
                <p className="text-text-secondary text-sm">Filter potentially explicit or unsafe content automatically</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable Safe Mode</p>
                  <p className="text-text-secondary text-sm mt-0.5">
                    {localSafeMode ? 'Content filtering is active' : 'Content filtering is disabled'}
                  </p>
                </div>
                <Switch checked={localSafeMode} onCheckedChange={setLocalSafeMode} />
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Gauge className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Sensitivity</span>
                  </div>
                  <span className="text-text-secondary text-sm">
                    {SENSITIVITY_LABELS[localSensitivity - 1]}
                  </span>
                </div>
                <Slider
                  value={[localSensitivity]}
                  onValueChange={([value]) => setLocalSensitivity(value)}
                  min={1}
                  max={5}
                  step={1}
                />
                <p className="text-text-muted text-xs mt-2">
                  Higher sensitivity flags more content but may increase false positives
                </p>
              </div>

              <button
                onClick={handleSaveSafeMode}
                disabled={isSaving}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {isSaving ? 'Saving...' : 'Save Safe Mode'}
              </button>
            </div>
          </div>

          {/* Keyword Blacklist */}
          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-status-warning/20">
                <AlertTriangle className="w-5 h-5 text-status-warning" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Keyword Blacklist</h2>
                <p className="text-text-secondary text-sm">Block content containing specific words or phrases</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <AnimatePresence>
                  {blacklist.map((word) => (
                    <motion.div
                      key={word}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-status-warning/10 border border-status-warning/30"
                    >
                      <span className="text-text-primary text-sm">{word}</span>
                      <button
                        onClick={() => handleRemoveKeyword(word)}
                        className="text-text-muted hover:text-status-error transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </motion.div>
                  ))}
                </AnimatePresence>
                {blacklist.length === 0 && (
                  <p className="text-text-muted text-sm">No blocked keywords yet</p>
                )}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={newKeyword}
                  onChange={(e) => setNewKeyword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddKeyword();
                  }}
                  placeholder="Add a keyword..."
                  className="flex-1 px-4 py-2.5 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
                />
                <button
                  onClick={handleAddKeyword}
                  disabled={!newKeyword.trim()}
                  className="px-4 py-2.5 rounded-lg bg-bg-tertiary border border-white/10 text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Add
                </button>
              </div>
            </div>
          </div>

          {/* Change PIN */}
          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Key className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Change PIN</h2>
                <p className="text-text-secondary text-sm">Update your 4-digit safety PIN</p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">New PIN</label>
                <input
                  type="password"
                  inputMode="numeric"
                  maxLength={4}
                  value={newPin}
                  onChange={(e) => {
                    const val = e.target.value.replace(/\D/g, '').slice(0, 4);
                    setNewPin(val);
                    setPinErrorMsg('');
                  }}
                  placeholder="••••"
                  className="w-full px-4 py-2.5 bg-bg-tertiary border border-white/10 rounded-lg text-white text-center text-xl tracking-[0.5em] placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Confirm PIN</label>
                <input
                  type="password"
                  inputMode="numeric"
                  maxLength={4}
                  value={confirmPin}
                  onChange={(e) => {
                    const val = e.target.value.replace(/\D/g, '').slice(0, 4);
                    setConfirmPin(val);
                    setPinErrorMsg('');
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleChangePin();
                  }}
                  placeholder="••••"
                  className="w-full px-4 py-2.5 bg-bg-tertiary border border-white/10 rounded-lg text-white text-center text-xl tracking-[0.5em] placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
                />
              </div>

              {pinErrorMsg && <p className="text-status-error text-sm">{pinErrorMsg}</p>}

              <button
                onClick={handleChangePin}
                disabled={isSaving}
                className="px-4 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {isSaving ? 'Updating...' : 'Update PIN'}
              </button>
            </div>
          </div>

          {/* Quarantined Content */}
          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-status-warning/20">
                <ShieldCheck className="w-5 h-5 text-status-warning" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Quarantined Content</h2>
                <p className="text-text-secondary text-sm">
                  {quarantined.length} item{quarantined.length !== 1 ? 's' : ''} flagged by safe mode
                </p>
              </div>
            </div>

            {quarantined.length === 0 ? (
              <div className="text-center py-12">
                <ShieldCheck className="w-12 h-12 text-status-success mx-auto mb-3" />
                <p className="text-text-primary font-medium">Nothing quarantined</p>
                <p className="text-text-secondary text-sm">All content passes safety checks</p>
              </div>
            ) : (
              <div className="space-y-3">
                <AnimatePresence>
                  {quarantined.map((item) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="flex items-center gap-4 p-4 rounded-lg bg-bg-tertiary/50 border border-border"
                    >
                      {item.thumbnail ? (
                        <img
                          src={item.thumbnail}
                          alt={item.title}
                          className="w-16 h-16 rounded-lg object-cover bg-bg-tertiary"
                        />
                      ) : (
                        <div className="w-16 h-16 rounded-lg bg-bg-tertiary flex items-center justify-center">
                          <AlertTriangle className="w-6 h-6 text-text-muted" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-text-primary font-medium truncate">{item.title}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-status-warning/20 text-status-warning">
                            {item.reason}
                          </span>
                          <span className="text-text-muted text-xs">
                            {new Date(item.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleRestore(item.id)}
                          disabled={isSaving}
                          className="p-2 rounded-lg bg-status-success/10 text-status-success hover:bg-status-success/20 disabled:opacity-50 transition-colors"
                          title="Restore"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                        {purgeConfirmId === item.id ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-status-error whitespace-nowrap">Delete forever?</span>
                            <button
                              onClick={() => handlePurge(item.id)}
                              className="px-2 py-1 rounded bg-status-error text-white text-xs hover:opacity-90"
                            >
                              Yes
                            </button>
                            <button
                              onClick={() => setPurgeConfirmId(null)}
                              className="px-2 py-1 rounded bg-bg-tertiary text-text-secondary text-xs hover:text-text-primary"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setPurgeConfirmId(item.id)}
                            disabled={isSaving}
                            className="p-2 rounded-lg bg-status-error/10 text-status-error hover:bg-status-error/20 disabled:opacity-50 transition-colors"
                            title="Delete Forever"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>
      )}
      </div>
    </FeatureGuard>
  );
}
