chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'save-to-mediavault',
    title: 'Save to MediaVault',
    contexts: ['link', 'page'],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'save-to-mediavault') return;

  const url = info.linkUrl || info.pageUrl;
  if (!url) return;

  const [storage] = await chrome.storage.sync.get('backendUrl');
  const backendUrl = (storage && storage.backendUrl ? storage.backendUrl : 'http://localhost:8000').replace(/\/$/, '');

  try {
    const response = await fetch(`${backendUrl}/api/v1/downloads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    if (response.status === 202) {
      chrome.tabs.sendMessage(tab.id, { action: 'toast', text: 'Sent to MediaVault ✅' }).catch(() => {});
    } else if (response.status === 409) {
      chrome.tabs.sendMessage(tab.id, { action: 'toast', text: 'Already queued / duplicate' }).catch(() => {});
    } else {
      chrome.tabs.sendMessage(tab.id, { action: 'toast', text: `Error ${response.status}` }).catch(() => {});
    }
  } catch (err) {
    chrome.tabs.sendMessage(tab.id, { action: 'toast', text: 'Could not reach MediaVault backend' }).catch(() => {});
  }
});
