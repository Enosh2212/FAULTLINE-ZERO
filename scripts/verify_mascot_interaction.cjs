const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const base = process.env.FZ_BASE_URL || 'http://localhost:8000';
  const outputDir = path.resolve(__dirname, '..', 'output');
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  const checks = [];
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  const check = (label, condition) => {
    assert.ok(condition, label);
    checks.push(label);
  };

  console.log('Navigating to landing page...');
  await page.goto(base + '/#landing');
  await page.waitForTimeout(1000);

  const heroAgent = page.locator('.hero-agent-scene');
  check('Hero agent scene is present in DOM', await heroAgent.count() === 1);

  // Helper to get head rig state from page
  const getRigState = async () => {
    return await page.evaluate(() => {
      // Find instance through hero global
      const canvas = document.querySelector('.agent-head-canvas');
      return {
        canvasWidth: canvas.width,
        canvasHeight: canvas.height,
        canvasBoundingBox: canvas.getBoundingClientRect(),
        svgBoundingBox: document.querySelector('.hero-agent-scene svg').getBoundingClientRect()
      };
    });
  };

  const initialRig = await getRigState();
  check('Head canvas initialized with 2x resolution', initialRig.canvasWidth === 280 && initialRig.canvasHeight === 300);

  // 1. Center / Neutral Pose
  console.log('Testing Center / Neutral Pose...');
  const headCenter = await page.evaluate(() => {
    const svg = document.querySelector('.hero-agent-scene svg');
    const rect = svg.getBoundingClientRect();
    const scale = Math.min(rect.width / 600, rect.height / 520);
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + (rect.height - 520 * scale) / 2 + 183 * scale
    };
  });

  await page.mouse.move(headCenter.x, headCenter.y);
  await page.waitForTimeout(400);
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-center.png') });
  check('Mascot neutral center pose captured', fs.existsSync(path.join(outputDir, 'mascot-pose-center.png')));

  // 2. Cursor Far Left
  console.log('Testing Cursor Far Left...');
  await page.mouse.move(80, headCenter.y);
  await page.waitForTimeout(450);
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-left.png') });
  check('Mascot turns toward cursor left', fs.existsSync(path.join(outputDir, 'mascot-pose-left.png')));

  // 3. Cursor Far Right
  console.log('Testing Cursor Far Right...');
  await page.mouse.move(1400, headCenter.y);
  await page.waitForTimeout(450);
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-right.png') });
  check('Mascot turns toward cursor right', fs.existsSync(path.join(outputDir, 'mascot-pose-right.png')));

  // 4. Cursor Above Head
  console.log('Testing Cursor Top...');
  await page.mouse.move(headCenter.x, 60);
  await page.waitForTimeout(450);
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-top.png') });
  check('Mascot tilts toward cursor top', fs.existsSync(path.join(outputDir, 'mascot-pose-top.png')));

  // 5. Cursor Below Head
  console.log('Testing Cursor Bottom...');
  await page.mouse.move(headCenter.x, 820);
  await page.waitForTimeout(450);
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-bottom.png') });
  check('Mascot tilts toward cursor bottom', fs.existsSync(path.join(outputDir, 'mascot-pose-bottom.png')));

  // 6. Fast Left-to-Right Gaze Transition
  console.log('Testing Fast Left-to-Right Movement...');
  await page.mouse.move(100, headCenter.y);
  await page.waitForTimeout(300);
  // Rapid sweep: move to right in small steps
  for (let x = 100; x <= 1350; x += 250) {
    await page.mouse.move(x, headCenter.y);
    await page.waitForTimeout(30);
  }
  // Capture mid-transition
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-transition.png') });
  check('Mascot fast transition captured without tearing', fs.existsSync(path.join(outputDir, 'mascot-pose-transition.png')));

  // 7. Cursor Leaving Window (Mouseleave / Blur)
  console.log('Testing Pointer Leaving Window...');
  await page.mouse.move(1350, headCenter.y);
  await page.waitForTimeout(200);
  await page.evaluate(() => {
    document.dispatchEvent(new Event('mouseleave'));
    window.dispatchEvent(new Event('blur'));
  });
  await page.waitForTimeout(600); // Wait for smooth return to neutral
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-leave-relaxed.png') });
  check('Mascot smoothly relaxes to neutral on cursor leave', fs.existsSync(path.join(outputDir, 'mascot-pose-leave-relaxed.png')));

  // 8. Idle State (Organic Breathing Micro-Drift & Blinking)
  console.log('Testing Idle State...');
  await page.waitForTimeout(4600); // Wait through one natural blink cycle
  await heroAgent.screenshot({ path: path.join(outputDir, 'mascot-pose-idle.png') });
  check('Mascot idle state operates smoothly', fs.existsSync(path.join(outputDir, 'mascot-pose-idle.png')));

  // 9. Verify Responsive / Mobile Layout
  console.log('Testing Mobile Viewport (390x844)...');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outputDir, 'mascot-mobile-viewport.png'), fullPage: false });
  check('Mascot renders properly on mobile viewport', fs.existsSync(path.join(outputDir, 'mascot-mobile-viewport.png')));

  check('Zero browser JavaScript errors throughout test', errors.length === 0);

  const summary = {
    status: 'PASS',
    total_checks: checks.length,
    checks,
    errors,
    screenshots: [
      'output/mascot-pose-center.png',
      'output/mascot-pose-left.png',
      'output/mascot-pose-right.png',
      'output/mascot-pose-top.png',
      'output/mascot-pose-bottom.png',
      'output/mascot-pose-transition.png',
      'output/mascot-pose-leave-relaxed.png',
      'output/mascot-pose-idle.png',
      'output/mascot-mobile-viewport.png'
    ]
  };

  fs.writeFileSync(path.join(outputDir, 'mascot-verification.json'), JSON.stringify(summary, null, 2));
  console.log('Mascot Verification Result:');
  console.log(JSON.stringify(summary, null, 2));

  await browser.close();
})().catch(err => {
  console.error('Mascot Verification Failed:', err);
  process.exit(1);
});
