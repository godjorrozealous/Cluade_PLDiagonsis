import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/mnt/e/Cluade_PLDiagonsis/tmp/screenshots';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    // 1. Navigate to the app
    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01-initial-load.png`, fullPage: true });
    console.log('Screenshot saved: 01-initial-load.png');

    // 2. Check for the skills/strategy panel on the right
    const strategyPanel = page.locator('text=策略管理');
    const hasStrategyPanel = await strategyPanel.isVisible().catch(() => false);
    console.log('Strategy panel (策略管理) visible:', hasStrategyPanel);

    // 3. List all strategy names found
    const allText = await page.locator('.strategy-panel, [class*="strategy"], [class*="skill"]').allTextContents().catch(() => []);
    console.log('Strategy/Skill panel text contents:', allText);

    // Get all text from the right side panel area
    const rightPanelTexts = await page.locator('text=/./').allTextContents();
    console.log('All text on page (first 50):', rightPanelTexts.slice(0, 50));

    // 4. Check for specific skills
    const skillsToCheck = ['行波测距分析', '保护动作分析', '气象关联分析', 'comprehensive_diagnosis'];
    for (const skill of skillsToCheck) {
      const found = await page.locator(`text=${skill}`).isVisible().catch(() => false);
      console.log(`Skill "${skill}" visible:`, found);
    }

    // 5. Look for status badges (已启用 / 已禁用)
    const enabledBadges = page.locator('text=已启用');
    const disabledBadges = page.locator('text=已禁用');
    const enabledCount = await enabledBadges.count();
    const disabledCount = await disabledBadges.count();
    console.log('已启用 badges:', enabledCount);
    console.log('已禁用 badges:', disabledCount);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/02-skills-detail.png`, fullPage: true });
    console.log('Screenshot saved: 02-skills-detail.png');

    // 6. Try clicking the first "已启用" or "已禁用" badge as a toggle
    const allBadges = page.locator('text=已启用, text=已禁用');
    const totalBadges = await page.locator('text=/已启用|已禁用/').count();
    console.log('Total status badges:', totalBadges);

    if (totalBadges > 0) {
      const firstBadge = page.locator('text=/已启用|已禁用/').first();
      const badgeText = await firstBadge.textContent();
      console.log('Clicking first badge with text:', badgeText);
      await firstBadge.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/03-after-toggle-click.png`, fullPage: true });
      console.log('Screenshot saved: 03-after-toggle-click.png');

      // Click again to toggle back
      await firstBadge.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/04-after-toggle-back.png`, fullPage: true });
      console.log('Screenshot saved: 04-after-toggle-back.png');
    }

    // 7. Look for refresh button - try icon buttons or text
    const refreshBtn = page.locator('button').filter({ hasText: /刷新|Refresh|↻|⟳/ });
    const refreshCount = await refreshBtn.count();
    console.log('Refresh buttons found:', refreshCount);

    // Also look for any button with icon
    const allButtons = await page.locator('button').all();
    console.log('Total buttons on page:', allButtons.length);
    for (let i = 0; i < Math.min(allButtons.length, 10); i++) {
      const text = await allButtons[i].textContent();
      const title = await allButtons[i].getAttribute('title');
      console.log(`Button ${i}: text="${text?.trim()}", title="${title}"`);
    }

    // Final screenshot
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05-final-state.png`, fullPage: true });
    console.log('Screenshot saved: 05-final-state.png');

    // Print summary
    console.log('\n=== SKILLS UI TEST SUMMARY ===');
    console.log('Page loaded: true');
    console.log('Strategy panel (策略管理) visible:', hasStrategyPanel);
    console.log('已启用 badges:', enabledCount);
    console.log('已禁用 badges:', disabledCount);
    console.log('Total status badges:', totalBadges);

    await page.waitForTimeout(2000);
  } catch (err) {
    console.error('Error during test:', err);
  } finally {
    await browser.close();
  }
})();
