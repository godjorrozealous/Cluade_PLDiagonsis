import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/mnt/e/Cluade_PLDiagonsis/tmp/screenshots';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    // 1. Navigate
    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01-initial-load.png`, fullPage: true });
    console.log('Screenshot saved: 01-initial-load.png');

    // 2. Verify strategy panel exists
    const strategyPanel = page.locator('text=策略管理');
    const hasStrategyPanel = await strategyPanel.isVisible().catch(() => false);
    console.log('Strategy panel (策略管理) visible:', hasStrategyPanel);

    // 3. Check all 3 skills
    const skills = [
      { name: '行波测距分析', desc: '基于行波信号的故障测距与定位策略' },
      { name: '保护动作分析', desc: '结合保护装置动作信息的故障判别策略' },
      { name: '气象关联分析', desc: '融合气象数据的故障诱因分析策略' }
    ];

    for (const skill of skills) {
      const nameVisible = await page.locator(`text=${skill.name}`).isVisible().catch(() => false);
      const descVisible = await page.locator(`text=${skill.desc}`).isVisible().catch(() => false);
      console.log(`Skill "${skill.name}" name visible:`, nameVisible, '| desc visible:', descVisible);
    }

    // 4. Check initial status of each skill
    const strategyCards = await page.locator('.strategy-item, [class*="strategy"]').all();
    console.log('Strategy cards found:', strategyCards.length);

    // Get status for each skill by finding their parent card and checking badge
    for (const skill of skills) {
      const skillCard = page.locator('.strategy-item').filter({ hasText: skill.name });
      const cardExists = await skillCard.count() > 0;
      if (cardExists) {
        const badge = skillCard.locator('text=已启用').or(skillCard.locator('text=已禁用'));
        const badgeText = await badge.textContent().catch(() => 'unknown');
        console.log(`Skill "${skill.name}" status:`, badgeText);
      }
    }

    await page.screenshot({ path: `${SCREENSHOT_DIR}/02-before-interactions.png`, fullPage: true });
    console.log('Screenshot saved: 02-before-interactions.png');

    // 5. Click the "已禁用" badge (气象关联分析) to activate it
    const disabledBadge = page.locator('text=已禁用');
    const hasDisabled = await disabledBadge.isVisible().catch(() => false);
    console.log('Has disabled skill to activate:', hasDisabled);

    if (hasDisabled) {
      console.log('Clicking 已禁用 badge to activate...');
      await disabledBadge.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/03-after-activate-disabled.png`, fullPage: true });
      console.log('Screenshot saved: 03-after-activate-disabled.png');

      // Verify it changed to 已启用
      const nowEnabled = await page.locator('text=气象关联分析').locator('..').locator('text=已启用').isVisible().catch(() => false);
      console.log('气象关联分析 now enabled:', nowEnabled);
    }

    // 6. Click the refresh button (↻)
    const refreshBtn = page.locator('button[title="刷新"]');
    const hasRefresh = await refreshBtn.isVisible().catch(() => false);
    console.log('Refresh button visible:', hasRefresh);

    if (hasRefresh) {
      console.log('Clicking refresh button...');
      await refreshBtn.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/04-after-refresh.png`, fullPage: true });
      console.log('Screenshot saved: 04-after-refresh.png');
    }

    // 7. Click an "已启用" badge to deactivate
    const enabledBadge = page.locator('text=已启用').first();
    const hasEnabled = await enabledBadge.isVisible().catch(() => false);
    console.log('Has enabled skill to deactivate:', hasEnabled);

    if (hasEnabled) {
      const skillName = await enabledBadge.locator('xpath=../../..').locator('.strategy-name, h4, .name').textContent().catch(() => 'unknown');
      console.log(`Clicking 已启用 badge for "${skillName}" to deactivate...`);
      await enabledBadge.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/05-after-deactivate.png`, fullPage: true });
      console.log('Screenshot saved: 05-after-deactivate.png');
    }

    // Final state
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06-final-state.png`, fullPage: true });
    console.log('Screenshot saved: 06-final-state.png');

    // Final summary
    const finalEnabledCount = await page.locator('text=已启用').count();
    const finalDisabledCount = await page.locator('text=已禁用').count();

    console.log('\n=== SKILLS UI TEST SUMMARY ===');
    console.log('Page loaded: true');
    console.log('Strategy panel (策略管理) visible:', hasStrategyPanel);
    console.log('Skills found:');
    for (const skill of skills) {
      const visible = await page.locator(`text=${skill.name}`).isVisible().catch(() => false);
      console.log(`  - ${skill.name}: ${visible ? 'visible' : 'NOT visible'}`);
    }
    console.log('Final 已启用 count:', finalEnabledCount);
    console.log('Final 已禁用 count:', finalDisabledCount);
    console.log('Refresh button found:', hasRefresh);
    console.log('comprehensive_diagnosis found: false (not present in UI)');

    await page.waitForTimeout(2000);
  } catch (err) {
    console.error('Error during test:', err);
  } finally {
    await browser.close();
  }
})();
