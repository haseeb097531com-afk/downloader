(function () {
  'use strict';

  const urlInput = document.getElementById('backendUrl');
  const saveBtn = document.getElementById('save');
  const resetBtn = document.getElementById('reset');
  const status = document.getElementById('status');

  function setStatus(text) {
    status.textContent = text;
  }

  async function load() {
    const result = await chrome.storage.sync.get('backendUrl');
    if (result.backendUrl) urlInput.value = result.backendUrl;
  }

  async function saveBackendUrl() {
    const value = (urlInput.value || '').trim();
    if (!value) return;
    await chrome.storage.sync.set({ backendUrl: value });
    setStatus('Saved backend URL');
  }

  async function sendSave() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      setStatus('No active tab');
      return;
    }

    await saveBackendUrl();

    try {
      await chrome.tabs.sendMessage(tab.id, { action: 'save' });
      setStatus('Opening save flow...');
    } catch (err) {
      setStatus('Reload the page to enable saving here');
    }
  }

  saveBtn.addEventListener('click', async () => {
    await sendSave();
  });

  resetBtn.addEventListener('click', async () => {
    await chrome.storage.sync.remove('backendUrl');
    urlInput.value = '';
    setStatus('Reset to default');
  });

  load();
})();
