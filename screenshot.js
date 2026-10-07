const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function takeScreenshots() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  // Create screenshots directory
  const screenshotDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  // 1. FastAPI docs page
  console.log('Navigating to FastAPI docs...');
  await page.goto('http://127.0.0.1:8000/docs', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000); // Wait for UI to fully render
  
  // Take full page screenshot
  await page.screenshot({ 
    path: path.join(screenshotDir, 'fastapi-docs.png'), 
    fullPage: true 
  });
  console.log('FastAPI docs screenshot saved');

  // 2. Frontend home page
  console.log('Navigating to Frontend home...');
  await page.goto('http://127.0.0.1:3000/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000); // Wait for UI to fully render
  
  // Take full page screenshot
  await page.screenshot({ 
    path: path.join(screenshotDir, 'frontend-home.png'), 
    fullPage: true 
  });
  console.log('Frontend home screenshot saved');

  await browser.close();
  console.log('All screenshots completed!');
}

takeScreenshots().catch(console.error);