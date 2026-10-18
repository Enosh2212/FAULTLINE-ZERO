const { chromium } = require(process.env.FZ_PLAYWRIGHT_PATH || 'playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const base = process.env.FZ_BASE_URL || 'http://localhost:8000';
  const checks = [];
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  const check = (label, condition) => {
    assert.ok(condition, label);
    checks.push(label);
  };

  // 1. Navigate to Investigation Workspace
  await page.goto(base + '/#investigation');
  await page.waitForSelector('#change-select');
  await page.waitForSelector('#flymemory-disclosure');
  check('FlyMemory disclosure element exists in DOM', await page.locator('#flymemory-disclosure').count() === 1);

  // 2. Select change 'payment' and wait for change + flymemory to load
  await page.selectOption('#change-select', 'payment');
  await page.waitForTimeout(1000);

  // 3. Open disclosure
  const disclosure = page.locator('#flymemory-disclosure');
  await disclosure.locator('> summary').click();
  check('FlyMemory disclosure opens cleanly', await disclosure.evaluate(el => el.open));

  // 4. Verify disclosure header & bio badge
  const summaryText = await disclosure.locator('> summary').innerText();
  check('Disclosure has bio-inspired description', summaryText.includes('Bio-inspired associative memory'));
  check('FlyMemory container has bio-inspired badge', (await disclosure.textContent()).includes('FLYMEMORY // EXPERIMENTAL'));

  // 5. Verify toggle switch
  const toggle = page.locator('#flymemory-toggle');
  check('FlyMemory toggle switch exists', await toggle.count() === 1);

  // 6. Verify cards rendered
  const cards = page.locator('.flymemory-card');
  const cardCount = await cards.count();
  check('FlyMemory renders historical incident cards', cardCount > 0);

  const cardText = await cards.first().textContent();
  console.log('Sample card text:', cardText.replace(/\s+/g, ' ').trim());
  check('Card displays similarity score pill', cardText.toLowerCase().includes('pattern overlap') || cardText.includes('FalkorDB'));
  check('Card displays safety caveat', cardText.includes('Similarity hypothesis only') || cardText.includes('does not prove'));

  // 7. Check zero emoji compliance
  const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
  const allText = await disclosure.textContent();
  check('Zero emoji compliance in FlyMemory UI', !emojiRegex.test(allText));

  // 8. Capture desktop screenshot
  const outputDir = path.resolve(__dirname, '..', 'output');
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  await page.screenshot({ path: path.join(outputDir, 'flymemory-disclosure-desktop.png'), fullPage: true });

  // 9. Mobile viewport responsiveness
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);
  check('No horizontal page overflow on mobile', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: path.join(outputDir, 'flymemory-disclosure-mobile.png'), fullPage: true });

  check('Zero browser JavaScript errors', errors.length === 0);

  const result = {
    status: 'PASS',
    passed_checks: checks.length,
    checks,
    errors,
    card_count: cardCount,
  };

  fs.writeFileSync(path.join(outputDir, 'flymemory-ui-verification.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));

  await browser.close();
})().catch(err => {
  console.error('FlyMemory UI Verification Error:', err);
  process.exit(1);
});
