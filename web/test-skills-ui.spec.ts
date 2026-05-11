import { test, expect } from '@playwright/test';

const SCREENSHOT_DIR = '/mnt/e/Cluade_PLDiagonsis/tmp/screenshots';

test('skills UI end-to-end test', async ({ page }) => {
  // 1. Navigate to the app
  console.log('Navigating to http://localhost:5173...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/01-initial-load.png`, fullPage: true });
  console.log('Screenshot saved: 01-initial-load.png');

  // 2. Look for the skills panel
  const skillsPanel = page.locator('text=技能管理').or(page.locator('text=策略管理'));
  const hasSkillsPanel = await skillsPanel.isVisible().catch(() => false);
  console.log('Skills panel visible:', hasSkillsPanel);

  // Also try English labels
  const skillsPanelEn = page.locator('text=Skills').or(page.locator('text=Skill Management'));
  const hasSkillsPanelEn = await skillsPanelEn.isVisible().catch(() => false);
  console.log('Skills panel (English) visible:', hasSkillsPanelEn);

  // 3. Check for comprehensive_diagnosis skill
  const comprehensiveSkill = page.locator('text=comprehensive_diagnosis');
  const hasComprehensive = await comprehensiveSkill.isVisible().catch(() => false);
  console.log('comprehensive_diagnosis visible:', hasComprehensive);

  // 4. Look for any activate buttons (激活)
  const activateButtons = page.locator('button:has-text("激活"), button:has-text("Activate")');
  const activateCount = await activateButtons.count();
  console.log('Activate buttons found:', activateCount);

  // Take a screenshot of the current state
  await page.screenshot({ path: `${SCREENSHOT_DIR}/02-skills-panel-check.png`, fullPage: true });
  console.log('Screenshot saved: 02-skills-panel-check.png');

  // 5. Try clicking the first activate button if found
  if (activateCount > 0) {
    console.log('Clicking first activate button...');
    await activateButtons.first().click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03-after-activate-click.png`, fullPage: true });
    console.log('Screenshot saved: 03-after-activate-click.png');
  }

  // 6. Look for refresh button
  const refreshButton = page.locator('button:has-text("刷新"), button:has-text("Refresh")').or(
    page.locator('button[title*="refresh" i], button[aria-label*="refresh" i]')
  );
  const hasRefresh = await refreshButton.isVisible().catch(() => false);
  console.log('Refresh button visible:', hasRefresh);

  if (hasRefresh) {
    console.log('Clicking refresh button...');
    await refreshButton.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04-after-refresh.png`, fullPage: true });
    console.log('Screenshot saved: 04-after-refresh.png');
  }

  // Final screenshot
  await page.screenshot({ path: `${SCREENSHOT_DIR}/05-final-state.png`, fullPage: true });
  console.log('Screenshot saved: 05-final-state.png');

  // Print summary
  console.log('\n=== SKILLS UI TEST SUMMARY ===');
  console.log('Page loaded:', true);
  console.log('Skills panel (CN) visible:', hasSkillsPanel);
  console.log('Skills panel (EN) visible:', hasSkillsPanelEn);
  console.log('comprehensive_diagnosis visible:', hasComprehensive);
  console.log('Activate buttons found:', activateCount);
  console.log('Refresh button visible:', hasRefresh);
});
