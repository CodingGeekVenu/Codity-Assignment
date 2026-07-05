import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  console.log("Navigating to app...");
  await page.goto('http://192.168.29.78:5173');

  // Wait for jobs to load
  await page.waitForSelector('button[title="View Logs"]', { timeout: 10000 });
  console.log("Found View Logs button");
  
  // Click View Logs
  await page.click('button[title="View Logs"]');
  
  // Wait for logs to render
  console.log("Waiting for logs to render...");
  await page.waitForFunction(() => document.body.innerText.includes('Execution Logs'));
  await new Promise(r => setTimeout(r, 1000));
  
  await page.screenshot({ path: 'C:/Users/Venumadhav S/.gemini/antigravity/brain/367182fb-08fa-4abb-91f5-780f21b41467/logs_rendered.png' });
  console.log("Saved logs screenshot");

  // Navigate to DLQ
  console.log("Navigating to DLQ...");
  await page.evaluate(() => {
    const tabs = Array.from(document.querySelectorAll('button'));
    const dlqTab = tabs.find(el => el.textContent.includes('Dead Letter'));
    if(dlqTab) dlqTab.click();
  });
  
  await new Promise(r => setTimeout(r, 1000));
  
  // Actually the button contains a span with 'Retry'.
  console.log("Clicking Retry...");
  const clicked = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const retry = buttons.find(el => el.textContent.includes('Retry'));
    if(retry) {
      retry.click();
      return true;
    }
    return false;
  });
  
  console.log("Retry clicked?", clicked);

  await new Promise(r => setTimeout(r, 2000));
  
  // Go back to overview to see it queued
  await page.evaluate(() => {
    const tabs = Array.from(document.querySelectorAll('button'));
    const ov = tabs.find(el => el.textContent.includes('Overview'));
    if(ov) ov.click();
  });
  
  await new Promise(r => setTimeout(r, 1000));
  
  await page.screenshot({ path: 'C:/Users/Venumadhav S/.gemini/antigravity/brain/367182fb-08fa-4abb-91f5-780f21b41467/retry_clicked.png' });
  console.log("Saved overview screenshot after retry");

  await browser.close();
})();
