'use client';

import { useEffect, useState } from 'react';
import { lazy, Suspense } from 'react';
import { useDeviceStore } from '@/lib/store/device';
import {
  Smartphone,
  RefreshCw,
  Monitor,
  Trash2,
  Pencil,
  Check,
  X,
  QrCode,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { FeatureGuard } from '@/components/feature/FeatureGuard';

const QRCode = lazy(async () => {
  const mod = await import('qrcode.react');
  return { default: mod.QRCodeSVG };
});

const PERM_LABELS: Record<string, string> = {
  view: 'View',
  control: 'Control',
  scrape: 'Scrape',
};

export default function RemotePage() {
  const {
    pairData,
    isPairing,
    error,
    devices,
    startPair,
    pair,
    refreshDevices,
    updatePermissions,
    rename,
    revoke,
    clearPairData,
  } = useDeviceStore();

  const [name, setName] = useState('');
  const [perms, setPerms] = useState<string[]>(['view']);
  const [code, setCode] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [revokeId, setRevokeId] = useState<string | null>(null);

  useEffect(() => {
    refreshDevices();
  }, [refreshDevices]);

  useEffect(() => {
    if (!pairData) return;
    setCountdown(20);
    const t = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          clearInterval(t);
          clearPairData();
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [pairData, clearPairData]);

  const handleStartPair = async () => {
    if (!name.trim()) return;
    await startPair(name.trim(), perms);
  };

  const handleSubmitCode = async () => {
    if (!code.trim() || !name.trim()) return;
    await pair(code.trim(), name.trim());
    setCode('');
    setName('');
  };

  const togglePerm = (p: string) => {
    setPerms((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));
  };

  const startRename = (device: { id: string; name: string }) => {
    setEditingId(device.id);
    setEditName(device.name);
  };

  const submitRename = async (id: string) => {
    if (!editName.trim()) return;
    await rename(id, editName.trim());
    setEditingId(null);
  };

  const confirmRevoke = async (id: string) => {
    await revoke(id);
    setRevokeId(null);
  };

  const qrPayload = pairData ? `${pairData.code}` : '';

  return (
    <FeatureGuard featureKey="remote">
      <div className="max-w-4xl mx-auto p-4 sm:p-8 space-y-6">
      <div className="flex items-center gap-3">
        <Smartphone className="w-6 h-6 text-accent-primary" />
        <h1 className="text-3xl font-bold text-text-primary">Remote / Devices</h1>
      </div>

      {error && (
        <div className="glass-card rounded-xl p-4 border border-status-error/50 text-status-error text-sm">
          {error}
        </div>
      )}

      {!pairData ? (
        <div className="glass-card rounded-xl p-6 space-y-4">
          <h2 className="text-text-primary font-semibold text-lg">Pair a device</h2>
          <p className="text-text-secondary text-sm">
            Keep MediaVault Pro running on your desktop. Open this page on your phone and enter the code shown on your desktop.
          </p>
          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Device name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My iPhone"
              className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Permissions</label>
            <div className="flex flex-wrap gap-2">
              {Object.keys(PERM_LABELS).map((p) => {
                const active = perms.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => togglePerm(p)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                        : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {PERM_LABELS[p]}
                  </button>
                );
              })}
            </div>
          </div>
          <button
            onClick={handleStartPair}
            disabled={isPairing || !name.trim()}
            className="px-6 py-3 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity inline-flex items-center gap-2"
          >
            {isPairing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <QrCode className="w-4 h-4" />}
            Generate pairing code
          </button>
        </div>
      ) : (
        <div className="glass-card rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-text-primary font-semibold text-lg">Pairing code</h2>
            <span className="text-text-muted text-sm">Expires in {countdown}s</span>
          </div>
          <div className="flex flex-col md:flex-row items-center gap-6">
            <div className="flex-1 w-full">
              <p className="text-text-secondary text-sm mb-2">Enter this code on your phone:</p>
              <div className="bg-bg-tertiary border border-border rounded-xl p-6 text-center">
                <span className="text-4xl font-mono font-bold text-text-primary tracking-widest">
                  {pairData.code}
                </span>
              </div>
            </div>
            <div className="shrink-0">
              <Suspense fallback={<div className="w-48 h-48 bg-bg-tertiary rounded-xl animate-pulse" />}>
                <QRCode value={qrPayload} size={192} className="rounded-xl" />
              </Suspense>
            </div>
          </div>
          <div>
            <label className="block text-text-primary text-sm font-medium mb-2">Or type code on your phone</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Enter code"
                className="flex-1 px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
              />
              <button
                onClick={handleSubmitCode}
                disabled={!code.trim()}
                className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50"
              >
                Pair
              </button>
            </div>
          </div>
          <button
            onClick={clearPairData}
            className="text-text-muted hover:text-text-primary text-sm inline-flex items-center gap-1"
          >
            <X className="w-4 h-4" /> Cancel
          </button>
        </div>
      )}

      <div className="glass-card rounded-xl overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h3 className="text-text-primary font-semibold">Paired devices</h3>
          <button
            onClick={refreshDevices}
            className="p-2 rounded-lg hover:bg-bg-tertiary text-text-secondary hover:text-text-primary"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        {devices.length === 0 ? (
          <div className="p-8 text-center text-text-muted text-sm">No devices paired yet.</div>
        ) : (
          <div className="divide-y divide-border">
            {devices.map((device) => (
              <div key={device.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Monitor className="w-5 h-5 text-text-secondary" />
                    <div>
                      {editingId === device.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="px-2 py-1 bg-bg-tertiary border border-border rounded text-text-primary text-sm focus:outline-none focus:border-accent-primary"
                          />
                          <button onClick={() => submitRename(device.id)} className="p-1 text-status-success">
                            <Check className="w-4 h-4" />
                          </button>
                          <button onClick={() => setEditingId(null)} className="p-1 text-text-muted">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <p className="text-text-primary font-medium text-sm">{device.name}</p>
                          <p className="text-text-muted text-xs capitalize">{device.platform || 'desktop'}</p>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => startRename(device)}
                      className="p-2 rounded-md hover:bg-bg-tertiary text-text-secondary hover:text-text-primary"
                      title="Rename"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setRevokeId(device.id)}
                      className="p-2 rounded-md hover:bg-bg-tertiary text-status-error"
                      title="Revoke"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  {Object.keys(PERM_LABELS).map((p) => {
                    const active = device.permissions?.includes(p);
                    return (
                      <button
                        key={p}
                        onClick={async () => {
                          const next = active
                            ? device.permissions.filter((x: string) => x !== p)
                            : [...(device.permissions || []), p];
                          await updatePermissions(device.id, next);
                        }}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          active
                            ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                            : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        {PERM_LABELS[p]}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center justify-between mt-3 text-xs text-text-muted">
                  <span>Last seen: {new Date(device.last_seen).toLocaleString()}</span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-status-success animate-pulse" /> Active
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {revokeId && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setRevokeId(null)}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass-card rounded-xl p-6 max-w-sm w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-text-primary font-semibold mb-2">Revoke device?</h3>
            <p className="text-text-secondary text-sm mb-4">
              This will disconnect the device immediately. You can re-pair anytime.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setRevokeId(null)} className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary">
                Cancel
              </button>
              <button
                onClick={() => confirmRevoke(revokeId)}
                className="px-4 py-2 rounded-lg bg-status-error text-white hover:opacity-90"
              >
                Revoke
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
      </div>
    </FeatureGuard>
  );
}
