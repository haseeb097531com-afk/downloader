'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Wifi, WifiOff, Gauge, Clock } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { NetworkStatus, getNetworkStatus } from '@/lib/api/system';
import { useSettingsStore } from '@/lib/store/settings';

interface NetworkWidgetProps {
  compact?: boolean;
}

export function NetworkWidget({ compact = false }: NetworkWidgetProps) {
  const [network, setNetwork] = useState<NetworkStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const { settings } = useSettingsStore();

  const [localBandwidth, setLocalBandwidth] = useState(settings.max_bandwidth_mbps || 0);
  const [localAutoAdjust, setLocalAutoAdjust] = useState(settings.auto_adjust_quality || false);
  const [offPeakEnabled, setOffPeakEnabled] = useState(settings.off_peak_enabled || false);
  const [offPeakStart, setOffPeakStart] = useState(settings.off_peak_start || '22:00');
  const [offPeakEnd, setOffPeakEnd] = useState(settings.off_peak_end || '06:00');

  useEffect(() => {
    const fetchNetwork = async () => {
      try {
        const data = await getNetworkStatus();
        setNetwork(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    fetchNetwork();
    const interval = setInterval(fetchNetwork, 5000);
    return () => clearInterval(interval);
  }, []);

  const getSpeedColor = (speed: number) => {
    if (speed >= 30) return 'text-status-success';
    if (speed >= 10) return 'text-status-warning';
    return 'text-status-error';
  };

  const getQualityLabel = (speed: number) => {
    if (speed >= 30) return '1080p+';
    if (speed >= 10) return '720p';
    return '480p';
  };

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        {loading ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-tertiary/50 border border-border">
            <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }} className="w-3 h-3 rounded-full border border-accent-primary border-t-transparent" />
            <span className="text-xs text-text-muted">Checking...</span>
          </div>
        ) : network ? (
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
              network.speed_mbps < 10
                ? 'bg-status-warning/10 border-status-warning/30'
                : 'bg-bg-tertiary/50 border-border'
            }`}
            title={`Recommended quality: ${network.speed_mbps < 10 ? '480p' : network.speed_mbps < 30 ? '720p' : '1080p+'}\nLatency: ${network.latency_ms}ms`}
          >
            {network.is_online ? (
              <Wifi className={`w-4 h-4 ${getSpeedColor(network.speed_mbps)}`} />
            ) : (
              <WifiOff className="w-4 h-4 text-status-error" />
            )}
            <span className={`text-sm font-medium ${getSpeedColor(network.speed_mbps)}`}>
              {network.speed_mbps} Mbps
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-tertiary/50 border border-border">
            <WifiOff className="w-4 h-4 text-text-muted" />
            <span className="text-xs text-text-muted">Offline</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }} className="w-6 h-6 rounded-full border-2 border-accent-primary border-t-transparent" />
        </div>
      ) : network ? (
        <>
          <div className="flex items-center gap-3 p-4 rounded-xl bg-bg-tertiary/50 border border-border">
            <div className={`p-2 rounded-lg ${network.is_online ? 'bg-status-success/20' : 'bg-status-error/20'}`}>
              {network.is_online ? (
                <Wifi className={`w-5 h-5 ${getSpeedColor(network.speed_mbps)}`} />
              ) : (
                <WifiOff className="w-5 h-5 text-status-error" />
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-text-primary font-medium">Connection Speed</span>
                <span className={`text-lg font-bold ${getSpeedColor(network.speed_mbps)}`}>
                  {network.speed_mbps} Mbps
                </span>
              </div>
              <p className="text-text-secondary text-sm mt-0.5">
                Latency: {network.latency_ms}ms | Recommended: {getQualityLabel(network.speed_mbps)}
              </p>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-text-secondary" />
                <span className="text-text-primary font-medium">Bandwidth Limit</span>
              </div>
              <span className="text-text-secondary text-sm">
                {localBandwidth === 0 ? 'Unlimited' : `${localBandwidth} Mbps`}
              </span>
            </div>
            <Slider
              value={[localBandwidth]}
              onValueChange={([value]) => setLocalBandwidth(value)}
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
            <Switch checked={localAutoAdjust} onCheckedChange={setLocalAutoAdjust} />
          </div>

          <div className="pt-4 border-t border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-text-secondary" />
                <span className="text-text-primary font-medium">Off-Peak Scheduling</span>
              </div>
              <Switch checked={offPeakEnabled} onCheckedChange={setOffPeakEnabled} />
            </div>

            {offPeakEnabled && (
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="block text-text-secondary text-xs mb-1.5">Start Time</label>
                  <input
                    type="time"
                    value={offPeakStart}
                    onChange={(e) => setOffPeakStart(e.target.value)}
                    className="w-full px-3 py-2 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-text-secondary text-xs mb-1.5">End Time</label>
                  <input
                    type="time"
                    value={offPeakEnd}
                    onChange={(e) => setOffPeakEnd(e.target.value)}
                    className="w-full px-3 py-2 bg-bg-tertiary border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="text-center py-8 text-text-muted">
          <WifiOff className="w-8 h-8 mx-auto mb-2" />
          <p>Unable to detect network status</p>
        </div>
      )}
    </div>
  );
}
