'use client';

import { useEffect, useState } from 'react';
import { useSettingsStore } from '@/lib/store/settings';
import { useDesktopStore } from '@/lib/store/desktop';
import { usePushStore } from '@/lib/store/push';
import { getDiskStatus, DiskStatus, getSystemSpeed, SystemSpeed } from '@/lib/api/system';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Save, Loader2, Settings2, Cpu, HardDrive, Eye, EyeOff, Zap, Activity, Monitor, Shield, Cloud, Sparkles, CopyX, Globe2, Gauge, Clock, AlertTriangle, Bell } from 'lucide-react';
import { motion } from 'framer-motion';
import { getCloudStatus, getGoogleAuthUrl, connectDropbox, disconnectCloud, CloudStatus } from '@/lib/api/cloud';

const PROVIDER_COLORS: Record<string, string> = {
  scraperapi: 'bg-platform-youtube',
  zenrows: 'bg-platform-instagram',
  rapidapi: 'bg-status-info',
};

function getStatusColor(status: string) {
  if (status === 'near_limit' || status === 'exhausted') return 'text-status-error';
  if (status === 'no_key') return 'text-status-warning';
  return 'text-status-success';
}

function getBarColor(used: number, limit: number) {
  const ratio = used / limit;
  if (ratio >= 0.9) return 'bg-status-error';
  if (ratio >= 0.7) return 'bg-status-warning';
  return 'bg-status-success';
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function SettingsPage() {
  const {
    settings,
    isLoading,
    isSaving,
    fetchSettings,
    saveSettings,
    toasts,
    dismissToast,
    addToast,
    providers,
    attempts,
    testingProvider,
    isProvidersLoading,
    fetchProviders,
    runProviderTest,
  } = useSettingsStore();

  const {
    status: desktopStatus,
    fetchStatus: fetchDesktopStatus,
    startServices,
    stopServices,
    isStartingClipboard,
    isStoppingClipboard,
    isStartingTray,
    isStoppingTray,
  } = useDesktopStore();

  const [disk, setDisk] = useState<DiskStatus | null>(null);
  const [systemSpeed, setSystemSpeed] = useState<SystemSpeed | null>(null);

  const [localSettings, setLocalSettings] = useState(settings);
  const [showScraperKey, setShowScraperKey] = useState(false);
  const [showRapidKey, setShowRapidKey] = useState(false);
  const [showAttempts, setShowAttempts] = useState(false);

  const [cloudStatus, setCloudStatus] = useState<CloudStatus>({
    google_connected: false,
    dropbox_connected: false,
    cloud_backup_enabled: false,
    cloud_provider: null,
  });
  const [cloudProvider, setCloudProvider] = useState<'google' | 'dropbox'>('google');
  const [cloudEnabled, setCloudEnabled] = useState(false);
  const [dropboxToken, setDropboxToken] = useState('');
  const [isConnectingGoogle, setIsConnectingGoogle] = useState(false);
  const [isDisconnectingGoogle, setIsDisconnectingGoogle] = useState(false);
  const [isConnectingDropbox, setIsConnectingDropbox] = useState(false);
  const [isDisconnectingDropbox, setIsDisconnectingDropbox] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchProviders();
    fetchDesktopStatus();
  }, [fetchSettings, fetchProviders, fetchDesktopStatus]);

  useEffect(() => {
    const fetchCloud = async () => {
      try {
        const data = await getCloudStatus();
        setCloudStatus(data);
        setCloudEnabled(data.cloud_backup_enabled);
        if (data.cloud_provider) setCloudProvider(data.cloud_provider as 'google' | 'dropbox');
      } catch (e) {
        console.error(e);
      }
    };
    fetchCloud();
  }, []);

  useEffect(() => {
    const fetchDisk = async () => {
      try {
        const data = await getDiskStatus();
        setDisk(data);
      } catch (e) {
        console.error(e);
      }
    };
    fetchDisk();
    const interval = setInterval(fetchDisk, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchSpeed = async () => {
      try {
        const data = await getSystemSpeed();
        setSystemSpeed(data);
      } catch (e) {
        console.error(e);
      }
    };
    fetchSpeed();
    const interval = setInterval(fetchSpeed, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setLocalSettings(settings);
  }, [settings]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchProviders();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchProviders]);

  const handleSave = async () => {
    await saveSettings(localSettings);
    await fetchProviders();
  };

  const update = (patch: Record<string, unknown>) => {
    setLocalSettings((prev) => ({ ...prev, ...patch }));
  };

  const handleTestProvider = async (provider: string) => {
    await runProviderTest(provider);
  };

  const handleGoogleConnect = async () => {
    setIsConnectingGoogle(true);
    try {
      const data = await getGoogleAuthUrl();
      window.open(data.url, '_blank');
      addToast('Opening Google authorization...', 'info');
      setTimeout(() => getCloudStatus().then((d) => setCloudStatus(d)), 2000);
    } catch {
      addToast('Failed to connect Google Drive', 'error');
    } finally {
      setIsConnectingGoogle(false);
    }
  };

  const handleGoogleDisconnect = async () => {
    setIsDisconnectingGoogle(true);
    try {
      await disconnectCloud('google');
      addToast('Google Drive disconnected', 'success');
      getCloudStatus().then((d) => setCloudStatus(d));
    } catch {
      addToast('Failed to disconnect Google Drive', 'error');
    } finally {
      setIsDisconnectingGoogle(false);
    }
  };

  const handleDropboxConnect = async () => {
    if (!dropboxToken) return;
    setIsConnectingDropbox(true);
    try {
      await connectDropbox(dropboxToken);
      addToast('Dropbox connected', 'success');
      setDropboxToken('');
      getCloudStatus().then((d) => setCloudStatus(d));
    } catch {
      addToast('Failed to connect Dropbox', 'error');
    } finally {
      setIsConnectingDropbox(false);
    }
  };

  const handleDropboxDisconnect = async () => {
    setIsDisconnectingDropbox(true);
    try {
      await disconnectCloud('dropbox');
      addToast('Dropbox disconnected', 'success');
      getCloudStatus().then((d) => setCloudStatus(d));
    } catch {
      addToast('Failed to disconnect Dropbox', 'error');
    } finally {
      setIsDisconnectingDropbox(false);
    }
  };

  const sendTestPush = async () => {
    await usePushStore.getState().sendTest();
  };

  return (
    <div className="max-w-3xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Settings</h1>
        <p className="text-text-secondary">Configure post-processing, resource limits, and API fallback providers</p>
      </div>

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
          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-primary/20">
                <Settings2 className="w-5 h-5 text-accent-primary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Post-Processing</h2>
                <p className="text-text-secondary text-sm">Configure how downloaded media is processed</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Auto-merge Video & Audio</p>
                  <p className="text-text-secondary text-sm mt-0.5">Combines separate streams into a single MP4</p>
                </div>
                <Switch
                  checked={localSettings.auto_merge}
                  onCheckedChange={(checked) => update({ auto_merge: checked })}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Embed Metadata</p>
                  <p className="text-text-secondary text-sm mt-0.5">Adds title, creator, and date to file properties</p>
                </div>
                <Switch
                  checked={localSettings.embed_metadata}
                  onCheckedChange={(checked) => update({ embed_metadata: checked })}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Generate Local Thumbnails</p>
                  <p className="text-text-secondary text-sm mt-0.5">Extracts high-res thumbnails from the video</p>
                </div>
                <Switch
                  checked={localSettings.generate_thumbnails}
                  onCheckedChange={(checked) => update({ generate_thumbnails: checked })}
                />
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-status-warning/20">
                <Cpu className="w-5 h-5 text-status-warning" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Resource Guard</h2>
                <p className="text-text-secondary text-sm">Downloads will automatically pause if system resources exceed these limits.</p>
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Max CPU Usage</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.max_cpu_percent}%</span>
                </div>
                <Slider
                  value={[localSettings.max_cpu_percent]}
                  onValueChange={([value]) => update({ max_cpu_percent: value })}
                  min={10}
                  max={100}
                  step={10}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Max RAM Usage</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.max_ram_percent}%</span>
                </div>
                <Slider
                  value={[localSettings.max_ram_percent]}
                  onValueChange={([value]) => update({ max_ram_percent: value })}
                  min={10}
                  max={100}
                  step={10}
                />
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Zap className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Performance / Turbo Mode</h2>
                <p className="text-text-secondary text-sm">Multi-connection downloads for maximum speed</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Turbo Mode</p>
                  <p className="text-text-secondary text-sm mt-0.5">Uses multi-connection downloads for maximum speed</p>
                </div>
                <Switch
                  checked={localSettings.turbo_mode || false}
                  onCheckedChange={(checked) => update({ turbo_mode: checked })}
                />
              </div>

              {systemSpeed && !systemSpeed.aria2_available && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-status-warning/10 border border-status-warning/30">
                  <AlertTriangle className="w-4 h-4 text-status-warning" />
                  <span className="text-status-warning text-sm">aria2c not installed - using standard speed</span>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Gauge className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Parallel Fragments</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.concurrent_fragments}</span>
                </div>
                <Slider
                  value={[localSettings.concurrent_fragments]}
                  onValueChange={([value]) => update({ concurrent_fragments: value })}
                  min={1}
                  max={32}
                  step={1}
                />
                <p className="text-text-muted text-xs mt-2">Higher values may increase speed but use more connections</p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-primary/20">
                <Globe2 className="w-5 h-5 text-accent-primary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Network & Bandwidth</h2>
                <p className="text-text-secondary text-sm">Manage bandwidth limits and network-aware quality settings</p>
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Gauge className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Bandwidth Limit</span>
                  </div>
                  <span className="text-text-secondary text-sm">
                    {(localSettings.max_bandwidth_mbps || 0) === 0 ? 'Unlimited' : `${localSettings.max_bandwidth_mbps} Mbps`}
                  </span>
                </div>
                <Slider
                  value={[localSettings.max_bandwidth_mbps || 0]}
                  onValueChange={([value]) => update({ max_bandwidth_mbps: value })}
                  min={0}
                  max={100}
                  step={1}
                />
                <p className="text-text-muted text-xs mt-2">0 = Unlimited bandwidth usage</p>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Auto-Adjust Quality</p>
                  <p className="text-text-secondary text-sm mt-0.5">Automatically adjust quality based on network speed</p>
                </div>
                <Switch
                  checked={localSettings.auto_adjust_quality || false}
                  onCheckedChange={(checked) => update({ auto_adjust_quality: checked })}
                />
              </div>

              <div className="pt-4 border-t border-border">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Off-Peak Scheduling</span>
                  </div>
                  <Switch
                    checked={localSettings.off_peak_enabled || false}
                    onCheckedChange={(checked) => update({ off_peak_enabled: checked })}
                  />
                </div>

                {(localSettings.off_peak_enabled || false) && (
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <label className="block text-text-secondary text-xs mb-1.5">Off-Peak Start</label>
                      <input
                        type="time"
                        value={localSettings.off_peak_start || '22:00'}
                        onChange={(e) => update({ off_peak_start: e.target.value })}
                        className="w-full px-3 py-2 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-text-secondary text-xs mb-1.5">Off-Peak End</label>
                      <input
                        type="time"
                        value={localSettings.off_peak_end || '06:00'}
                        onChange={(e) => update({ off_peak_end: e.target.value })}
                        className="w-full px-3 py-2 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Zap className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">API Providers & Fallback</h2>
                <p className="text-text-secondary text-sm">Automatically switch to backup APIs when direct downloads are blocked</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable Smart Fallback</p>
                  <p className="text-text-secondary text-sm mt-0.5">Use backup APIs when direct extraction fails</p>
                </div>
                <Switch
                  checked={localSettings.fallback_enabled}
                  onCheckedChange={(checked) => update({ fallback_enabled: checked })}
                />
              </div>

              <div>
                <label className="block text-text-primary font-medium mb-2">Proxy Provider</label>
                <div className="flex gap-2">
                  {['scraperapi', 'zenrows'].map((provider) => (
                    <button
                      key={provider}
                      onClick={() => update({ scraper_provider: provider })}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-medium capitalize transition-all ${
                        localSettings.scraper_provider === provider
                          ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                          : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {provider}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-text-primary font-medium mb-2">
                  {localSettings.scraper_provider === 'zenrows' ? 'ZenRows' : 'ScraperAPI'} Key
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type={showScraperKey ? 'text' : 'password'}
                      value={localSettings.scraper_api_key}
                      onChange={(e) => update({ scraper_api_key: e.target.value })}
                      placeholder="Enter API key"
                      className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors pr-10"
                    />
                    <button
                      onClick={() => setShowScraperKey(!showScraperKey)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                    >
                      {showScraperKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <button
                    onClick={() => handleTestProvider(localSettings.scraper_provider)}
                    disabled={testingProvider !== null || !localSettings.scraper_api_key}
                    className="px-4 py-2.5 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors flex items-center gap-2"
                  >
                    {testingProvider === localSettings.scraper_provider ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      'Test'
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-text-primary font-medium mb-2">RapidAPI Key</label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type={showRapidKey ? 'text' : 'password'}
                      value={localSettings.rapid_api_key}
                      onChange={(e) => update({ rapid_api_key: e.target.value })}
                      placeholder="Enter RapidAPI key"
                      className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors pr-10"
                    />
                    <button
                      onClick={() => setShowRapidKey(!showRapidKey)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                    >
                      {showRapidKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <button
                    onClick={() => handleTestProvider('rapidapi')}
                    disabled={testingProvider !== null || !localSettings.rapid_api_key}
                    className="px-4 py-2.5 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors flex items-center gap-2"
                  >
                    {testingProvider === 'rapidapi' ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      'Test'
                    )}
                  </button>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-text-primary font-medium">Monthly Limit</span>
                  <span className="text-text-secondary text-sm">{localSettings.provider_monthly_limit}</span>
                </div>
                <Slider
                  value={[localSettings.provider_monthly_limit]}
                  onValueChange={([value]) => update({ provider_monthly_limit: value })}
                  min={100}
                  max={2000}
                  step={100}
                />
              </div>

              <div className="space-y-3">
                <p className="text-text-secondary text-sm font-medium">Usage</p>
                {isProvidersLoading ? (
                  <div className="space-y-2">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="h-4 bg-bg-tertiary rounded animate-pulse" />
                    ))}
                  </div>
                ) : (
                  providers.map((provider) => {
                    const ratio = provider.used_this_month / provider.monthly_limit;
                    const percentage = Math.min(ratio * 100, 100);
                    return (
                      <div key={provider.name} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${PROVIDER_COLORS[provider.name] || 'bg-bg-tertiary'}`} />
                            <span className="text-text-primary capitalize">{provider.name}</span>
                            {provider.status === 'near_limit' && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-status-warning/20 text-status-warning">
                                Near limit - will be skipped
                              </span>
                            )}
                          </div>
                          <span className={`text-xs font-mono ${getStatusColor(provider.status)}`}>
                            {provider.used_this_month} / {provider.monthly_limit}
                          </span>
                        </div>
                        <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                          <motion.div
                            className={`h-full rounded-full ${getBarColor(provider.used_this_month, provider.monthly_limit)}`}
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ duration: 0.5 }}
                          />
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <button
              onClick={() => setShowAttempts(!showAttempts)}
              className="flex items-center gap-3 w-full"
            >
              <div className="p-2 rounded-lg bg-status-info/20">
                <Activity className="w-5 h-5 text-status-info" />
              </div>
              <div className="flex-1 text-left">
                <h2 className="text-text-primary font-semibold">Recent Extraction Attempts</h2>
                <p className="text-text-secondary text-sm">Last 10 attempts from all providers</p>
              </div>
              <span className="text-text-muted text-sm">{showAttempts ? '▼' : '▶'}</span>
            </button>

            {showAttempts && (
              <div className="mt-4 space-y-2">
                {attempts.length === 0 ? (
                  <p className="text-text-secondary text-sm text-center py-8">
                    No extraction attempts yet - downloads will appear here.
                  </p>
                ) : (
                  attempts.map((attempt, index) => (
                    <div key={index} className="flex items-center gap-3 p-3 rounded-lg bg-bg-tertiary/50">
                      <div className={`w-2 h-2 rounded-full ${attempt.success ? 'bg-status-success' : 'bg-status-error'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs ${PROVIDER_COLORS[attempt.provider] || 'bg-bg-tertiary'} text-white capitalize`}>
                            {attempt.provider}
                          </span>
                          <span className="text-text-primary text-sm font-mono">{attempt.latency_ms}ms</span>
                        </div>
                        {attempt.error_message && (
                          <p className="text-status-error text-xs mt-1 truncate">{attempt.error_message}</p>
                        )}
                      </div>
                      <span className="text-text-muted text-xs">{timeAgo(attempt.created_at)}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="glass-card rounded-xl p-6" id="storage-guard">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-status-warning/20">
                <Shield className="w-5 h-5 text-status-warning" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Storage Guard</h2>
                <p className="text-text-secondary text-sm">
                  Automatically pause downloads when disk space is low
                </p>
              </div>
            </div>

            {disk && (
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-secondary text-sm">Disk Usage</span>
                  <span className="text-text-primary text-sm font-mono">
                    {disk.free_gb.toFixed(1)} GB free of {disk.total_gb.toFixed(1)} GB
                  </span>
                </div>
                <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${disk.used_percent}%`,
                      background:
                        disk.used_percent > 80
                          ? 'linear-gradient(90deg, #00B894 0%, #FDCB6E 50%, #FF6B6B 100%)'
                          : disk.used_percent > 60
                            ? 'linear-gradient(90deg, #00B894 0%, #FDCB6E 100%)'
                            : 'linear-gradient(90deg, #00B894 0%, #00D2FF 100%)',
                    }}
                  />
                </div>
              </div>
            )}

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable Storage Guard</p>
                  <p className="text-text-secondary text-sm mt-0.5">
                    Pause new downloads when free space drops below threshold
                  </p>
                </div>
                <Switch
                  checked={localSettings.storage_guard_enabled || false}
                  onCheckedChange={(checked) => update({ storage_guard_enabled: checked })}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Minimum Free Space</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.min_free_gb} GB</span>
                </div>
                <Slider
                  value={[localSettings.min_free_gb]}
                  onValueChange={([value]) => update({ min_free_gb: value })}
                  min={1}
                  max={50}
                  step={1}
                />
              </div>
            </div>

            {disk?.guard_active && (
              <div className="mt-6 p-4 rounded-xl bg-status-warning/10 border border-status-warning/30 flex items-start gap-3">
                <Shield className="w-5 h-5 text-status-warning shrink-0 mt-0.5" />
                <div>
                  <p className="text-status-warning font-medium text-sm">Storage low - downloads paused automatically</p>
                  <p className="text-text-secondary text-xs mt-1">
                    Free space is below your minimum threshold. Downloads will resume when space is freed.
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Sparkles className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">AI Analysis</h2>
                <p className="text-text-secondary text-sm">Transcribe audio, generate summaries and subtitles after each download</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable AI Analysis</p>
                  <p className="text-text-secondary text-sm mt-0.5">Run transcription and summarization automatically</p>
                </div>
                <Switch
                  checked={localSettings.ai_analysis_enabled || false}
                  onCheckedChange={(checked) => update({ ai_analysis_enabled: checked })}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Whisper Model</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.whisper_model}</span>
                </div>
                <div className="flex gap-2">
                  {['tiny', 'base', 'small', 'medium', 'large'].map((model) => (
                    <button
                      key={model}
                      onClick={() => update({ whisper_model: model })}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium capitalize transition-all ${
                        localSettings.whisper_model === model
                          ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                          : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {model}
                    </button>
                  ))}
                </div>
                <p className="text-text-muted text-xs mt-2">Larger models are more accurate but slower</p>
              </div>

              <div>
                <label className="block text-text-primary font-medium mb-2">Ollama Model</label>
                <input
                  type="text"
                  value={localSettings.ollama_model}
                  onChange={(e) => update({ ollama_model: e.target.value })}
                  placeholder="llama3"
                  className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
                />
              </div>

              <div>
                <label className="block text-text-primary font-medium mb-2">Auto-Translate Languages</label>
                <div className="flex flex-wrap gap-2">
                  {['en', 'ur', 'ar', 'hi', 'es', 'fr'].map((lang) => {
                    const isSelected = (localSettings.auto_translate_langs || []).includes(lang);
                    return (
                      <button
                        key={lang}
                        onClick={() => {
                          const current = localSettings.auto_translate_langs || [];
                          const next = isSelected
                            ? current.filter((l) => l !== lang)
                            : [...current, lang];
                          update({ auto_translate_langs: next });
                        }}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium uppercase transition-all ${
                          isSelected
                            ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                            : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        {lang}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6" id="desktop-integration">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Monitor className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Desktop Integration</h2>
                <p className="text-text-secondary text-sm">
                  Connect clipboard and system tray for instant downloads
                </p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable Clipboard Monitor</p>
                  <p className="text-text-secondary text-sm mt-0.5">
                    Watches your clipboard for supported links
                  </p>
                </div>
                <Switch
                  checked={desktopStatus?.clipboard_enabled || false}
                  onCheckedChange={(checked) => {
                    if (checked) startServices('clipboard');
                    else stopServices('clipboard');
                  }}
                  disabled={isStartingClipboard || isStoppingClipboard}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable System Tray</p>
                  <p className="text-text-secondary text-sm mt-0.5">
                    Run MediaVault in the background with system tray icon
                  </p>
                </div>
                <Switch
                  checked={desktopStatus?.tray_enabled || false}
                  onCheckedChange={(checked) => {
                    if (checked) startServices('tray');
                    else stopServices('tray');
                  }}
                  disabled={isStartingTray || isStoppingTray}
                />
              </div>
            </div>

            <div className="mt-6 pt-6 border-t border-border">
              <p className="text-text-secondary text-sm mb-3">Service Status</p>
              <div className="flex flex-wrap gap-3">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-tertiary/50 border border-border">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      desktopStatus?.clipboard_running
                        ? 'bg-status-success animate-pulse'
                        : 'bg-status-error'
                    }`}
                  />
                  <span className="text-text-secondary text-sm">Clipboard Monitor</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-tertiary/50 border border-border">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      desktopStatus?.tray_running
                        ? 'bg-status-success animate-pulse'
                        : 'bg-status-error'
                    }`}
                  />
                  <span className="text-text-secondary text-sm">System Tray</span>
                </div>
              </div>
              <p className="text-text-muted text-xs mt-3">
                When enabled, MediaVault watches your clipboard. Copy any supported link and a
                download prompt will appear instantly.
              </p>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Cloud className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Cloud Backup</h2>
                <p className="text-text-secondary text-sm">Sync downloads to Google Drive or Dropbox</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Auto-Backup Downloads</p>
                  <p className="text-text-secondary text-sm mt-0.5">Automatically back up new downloads to cloud</p>
                </div>
                <Switch
                  checked={cloudEnabled}
                  onCheckedChange={setCloudEnabled}
                />
              </div>

              <div>
                <label className="block text-text-primary font-medium mb-2">Provider</label>
                <div className="flex gap-2">
                  {(['google', 'dropbox'] as const).map((provider) => (
                    <button
                      key={provider}
                      onClick={() => setCloudProvider(provider)}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-medium capitalize transition-all ${
                        cloudProvider === provider
                          ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                          : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {provider === 'google' ? 'Google Drive' : 'Dropbox'}
                    </button>
                  ))}
                </div>
              </div>

              {cloudProvider === 'google' && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        cloudStatus.google_connected
                          ? 'bg-status-success/20 text-status-success'
                          : 'bg-bg-tertiary text-text-muted'
                      }`}
                    >
                      {cloudStatus.google_connected ? 'Connected' : 'Not connected'}
                    </span>
                  </div>
                  {cloudStatus.google_connected ? (
                    <button
                      onClick={handleGoogleDisconnect}
                      disabled={isDisconnectingGoogle}
                      className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
                    >
                      {isDisconnectingGoogle ? 'Disconnecting...' : 'Disconnect'}
                    </button>
                  ) : (
                    <button
                      onClick={handleGoogleConnect}
                      disabled={isConnectingGoogle}
                      className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
                    >
                      {isConnectingGoogle ? 'Connecting...' : 'Connect Google Drive'}
                    </button>
                  )}
                  <p className="text-text-muted text-xs">
                    After authorizing, this tab will show a confirmation. Return here and refresh.
                  </p>
                </div>
              )}

              {cloudProvider === 'dropbox' && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        cloudStatus.dropbox_connected
                          ? 'bg-status-success/20 text-status-success'
                          : 'bg-bg-tertiary text-text-muted'
                      }`}
                    >
                      {cloudStatus.dropbox_connected ? 'Connected' : 'Not connected'}
                    </span>
                  </div>
                  {cloudStatus.dropbox_connected ? (
                    <button
                      onClick={handleDropboxDisconnect}
                      disabled={isDisconnectingDropbox}
                      className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
                    >
                      {isDisconnectingDropbox ? 'Disconnecting...' : 'Disconnect'}
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <input
                          type="password"
                          value={dropboxToken}
                          onChange={(e) => setDropboxToken(e.target.value)}
                          placeholder="Enter Dropbox access token"
                          className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
                        />
                      </div>
                      <button
                        onClick={handleDropboxConnect}
                        disabled={isConnectingDropbox || !dropboxToken}
                        className="px-4 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
                      >
                        {isConnectingDropbox ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          'Connect'
                        )}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-secondary/20">
                <Globe2 className="w-5 h-5 text-accent-secondary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Network & Bandwidth</h2>
                <p className="text-text-secondary text-sm">Manage bandwidth limits and network-aware quality</p>
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Globe2 className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Bandwidth Limit</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.max_bandwidth_mbps} Mbps</span>
                </div>
                <Slider
                  value={[localSettings.max_bandwidth_mbps || 0]}
                  onValueChange={([value]) => update({ max_bandwidth_mbps: value })}
                  min={0}
                  max={100}
                  step={1}
                />
                <p className="text-text-muted text-xs mt-2">0 = Unlimited</p>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Auto-Adjust Quality by Network Speed</p>
                  <p className="text-text-secondary text-sm mt-0.5">Reduce quality when connection is slow</p>
                </div>
                <Switch
                  checked={localSettings.auto_adjust_quality || false}
                  onCheckedChange={(checked) => update({ auto_adjust_quality: checked })}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-text-primary font-medium">Off-Peak Downloads</span>
                  <Switch
                    checked={localSettings.off_peak_enabled || false}
                    onCheckedChange={(checked) => update({ off_peak_enabled: checked })}
                  />
                </div>
                {(localSettings.off_peak_enabled || false) && (
                  <div className="flex items-center gap-3 mt-3">
                    <div className="flex-1">
                      <label className="block text-text-secondary text-xs mb-1">Start Time</label>
                      <input
                        type="time"
                        value={localSettings.off_peak_start || '23:00'}
                        onChange={(e) => update({ off_peak_start: e.target.value })}
                        className="w-full px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary transition-colors"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-text-secondary text-xs mb-1">End Time</label>
                      <input
                        type="time"
                        value={localSettings.off_peak_end || '06:00'}
                        onChange={(e) => update({ off_peak_end: e.target.value })}
                        className="w-full px-3 py-2 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-primary transition-colors"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-status-warning/20">
                <CopyX className="w-5 h-5 text-status-warning" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Smart Deduplication</h2>
                <p className="text-text-secondary text-sm">Automatically detect and flag duplicate downloads</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable Duplicate Detection</p>
                  <p className="text-text-secondary text-sm mt-0.5">Check for duplicates before and after downloads</p>
                </div>
                <Switch
                  checked={localSettings.dedup_enabled || false}
                  onCheckedChange={(checked) => update({ dedup_enabled: checked })}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <CopyX className="w-4 h-4 text-text-secondary" />
                    <span className="text-text-primary font-medium">Match Sensitivity</span>
                  </div>
                  <span className="text-text-secondary text-sm">{localSettings.dedup_threshold}</span>
                </div>
                <Slider
                  value={[localSettings.dedup_threshold]}
                  onValueChange={([value]) => update({ dedup_threshold: value })}
                  min={0}
                  max={12}
                  step={1}
                />
                <p className="text-text-muted text-xs mt-2">
                  Lower = only near-identical videos flagged; higher = catches resized/re-encoded copies
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6" id="notifications-pwa">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-accent-primary/20">
                <Bell className="w-5 h-5 text-accent-primary" />
              </div>
              <div>
                <h2 className="text-text-primary font-semibold">Notifications &amp; PWA</h2>
                <p className="text-text-secondary text-sm">Manage push notifications and offline install</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Enable Push Notifications</p>
                  <p className="text-text-secondary text-sm mt-0.5">Receive browser push alerts for downloads</p>
                </div>
                <Switch
                  checked={localSettings.push_enabled || false}
                  onCheckedChange={(checked) => update({ push_enabled: checked })}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Permission</p>
                  <p className="text-text-secondary text-xs mt-0.5">
                    {typeof Notification !== 'undefined' ? Notification.permission : 'unsupported'}
                  </p>
                </div>
                <PermissionChip />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">Send Test Notification</p>
                  <p className="text-text-secondary text-sm mt-0.5">Trigger a browser notification now</p>
                </div>
                <button
                  onClick={sendTestPush}
                  disabled={isSaving}
                  className="px-4 py-2 rounded-lg bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
                >
                  Send Test
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-primary font-medium">App Install</p>
                  <p className="text-text-secondary text-sm mt-0.5">Install MediaVault as a desktop app</p>
                </div>
                <InstallStatus />
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-text-primary font-medium">Service Worker</p>
                    <p className="text-text-secondary text-xs mt-0.5">Offline caching and push listener</p>
                  </div>
                  <SWStatus />
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleSave}
              disabled={isSaving}
              className="px-6 py-3 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save Settings
                </>
              )}
            </motion.button>
          </div>
        </div>
      )}
    </div>
  );
}

function PermissionChip() {
  const { permission } = usePushStore();
  const [fixHint, setFixHint] = useState('');

  const request = async () => {
    const perm = await usePushStore.getState().ensurePermission();
    if (perm === 'denied') {
      setFixHint('Open browser settings → Site permissions → Notifications → Allow');
    }
  };

  const color =
    permission === 'granted'
      ? 'bg-status-success/20 text-status-success'
      : permission === 'denied'
        ? 'bg-status-error/20 text-status-error'
        : 'bg-bg-tertiary text-text-muted';

  return (
    <div className="text-right">
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${color}`}>{permission}</span>
      {permission !== 'granted' && (
        <button onClick={request} className="block text-xs text-accent-primary hover:underline mt-1">
          {permission === 'denied' ? 'Fix hint' : 'Request'}
        </button>
      )}
      {fixHint && <p className="text-xs text-text-muted mt-1">{fixHint}</p>}
    </div>
  );
}

function InstallStatus() {
  interface BeforeInstallPromptEvent extends Event {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
  }

  const [isInstalled, setIsInstalled] = useState(false);
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handler);
    setIsInstalled(window.matchMedia('(display-mode: standalone)').matches);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const install = async () => {
    if (!prompt) return;
    prompt.prompt();
    const { outcome } = await prompt.userChoice;
    if (outcome === 'accepted') setIsInstalled(true);
    setPrompt(null);
  };

  return (
    <div>
      {isInstalled ? (
        <span className="text-status-success text-sm">Installed</span>
      ) : prompt ? (
        <button onClick={install} className="px-4 py-2 rounded-lg bg-accent-primary text-white text-sm hover:opacity-90">
          Install App
        </button>
      ) : (
        <span className="text-text-muted text-sm">Not available</span>
      )}
    </div>
  );
}

function SWStatus() {
  const { swRegistration, updateAvailable, installUpdate } = usePushStore();
  return (
    <div className="text-right">
      <span className={`text-xs ${swRegistration ? 'text-status-success' : 'text-text-muted'}`}>
        {swRegistration ? 'Registered' : 'Unavailable'}
      </span>
      {updateAvailable && (
        <button onClick={installUpdate} className="block text-xs text-accent-primary hover:underline mt-1">
          Update available — click to reload
        </button>
      )}
    </div>
  );
}

