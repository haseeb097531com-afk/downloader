(function () {
  'use strict';

  const PLATFORM_MAP = {
    'youtube.com': 'youtube',
    'm.youtube.com': 'youtube',
    'tiktok.com': 'tiktok',
    'instagram.com': 'instagram',
    'facebook.com': 'facebook',
    'twitter.com': 'twitter',
    'x.com': 'twitter',
  };

  function getPlatform() {
    const host = window.location.hostname.replace(/^www\./, '');
    return PLATFORM_MAP[host] || null;
  }

  function getVideoUrl() {
    const platform = getPlatform();
    if (!platform) return null;

    if (platform === 'youtube') {
      const params = new URLSearchParams(window.location.search);
      const videoId = params.get('v');
      if (videoId) return `https://www.youtube.com/watch?v=${videoId}`;
      const shorts = window.location.pathname.match(/\/shorts\/([^\/?]+)/);
      if (shorts) return `https://www.youtube.com/watch?v=${shorts[1]}`;
      return null;
    }

    if (platform === 'tiktok') {
      const m = window.location.pathname.match(/\/video\/(\d+)/);
      if (m) return `https://www.tiktok.com/video/${m[1]}`;
      return null;
    }

    if (platform === 'instagram') {
      const m = window.location.pathname.match(/\/reel\/([^\/?]+)/);
      if (m) return `https://www.instagram.com/reel/${m[1]}`;
      return null;
    }

    if (platform === 'facebook') {
      const m = window.location.pathname.match(/\/watch\/?\?v=([^&]+)/) ||
                window.location.pathname.match(/\/(\d+)\/?$/);
      if (m) return window.location.origin + window.location.pathname;
      return null;
    }

    if (platform === 'twitter') {
      const m = window.location.pathname.match(/\/status\/(\d+)/);
      if (m) return `https://twitter.com/i/status/${m[1]}`;
      return null;
    }

    return null;
  }

  function showToast(message) {
    const existing = document.getElementById('mv-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'mv-toast';
    toast.textContent = message;
    Object.assign(toast.style, {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      background: '#16a34a',
      color: '#fff',
      padding: '10px 16px',
      borderRadius: '10px',
      fontSize: '14px',
      fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif',
      zIndex: '2147483647',
      boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
      transition: 'opacity 0.3s ease',
    });
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 2500);
  }

  async function getBackendUrl() {
    const result = await chrome.storage.sync.get('backendUrl');
    return (result.backendUrl || 'http://localhost:8000').replace(/\/$/, '');
  }

  async function sendToMediaVault() {
    const videoUrl = getVideoUrl();
    if (!videoUrl) {
      showToast('No video URL detected on this page');
      return;
    }

    const backendUrl = await getBackendUrl();
    const btn = document.getElementById('mv-save-btn');
    if (btn) btn.disabled = true;

    try {
      const response = await fetch(`${backendUrl}/api/v1/downloads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: videoUrl }),
      });

      if (response.status === 202) {
        showToast('Sent to MediaVault ✅');
      } else if (response.status === 409) {
        showToast('Already queued / duplicate');
      } else {
        const text = await response.text();
        showToast(`Error ${response.status}: ${text.slice(0, 120)}`);
      }
    } catch (err) {
      showToast('Could not reach MediaVault backend');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function injectButton() {
    if (document.getElementById('mv-save-btn')) return;

    const videoUrl = getVideoUrl();
    if (!videoUrl) return;

    const btn = document.createElement('button');
    btn.id = 'mv-save-btn';
    btn.textContent = '⬇ Save to MediaVault';
    Object.assign(btn.style, {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      zIndex: '2147483647',
      background: 'linear-gradient(135deg,#6366f1,#a855f7)',
      color: '#fff',
      border: 'none',
      padding: '10px 16px',
      borderRadius: '10px',
      fontSize: '14px',
      fontWeight: '600',
      cursor: 'pointer',
      fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif',
      boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
    });

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      sendToMediaVault();
    });

    document.body.appendChild(btn);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }

  const observer = new MutationObserver(() => injectButton());
  observer.observe(document.body, { childList: true, subtree: true });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg && msg.action === 'save') sendToMediaVault();
  });
})();
