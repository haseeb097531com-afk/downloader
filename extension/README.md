# MediaVault Saver (browser extension)

Minimal Manifest V3 extension that sends the current video page to your running MediaVault backend.

## Install (Chrome / Edge / Brave)

1. Open the browser and go to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select this `extension/` folder

## Use

- On a supported video page (YouTube, TikTok, Instagram, Facebook, Twitter/X) a floating **"Save to MediaVault"** button appears.
- Right-click any link or page and choose **Save to MediaVault**.
- Click the extension icon to change the backend URL (default `http://localhost:8000`).

## Files

- `manifest.json` - Manifest V3 config
- `content.js` - Floating button + toast on video pages
- `popup.html` + `popup.js` - Backend URL config popup
- `background.js` - Context-menu wiring
