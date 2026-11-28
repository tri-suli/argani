import { expect, test, type Page } from '@playwright/test';
import { mockRounds, reviewPath, ROUND_1, ROUND_2, ROUND_3_HUMAN, ROUND_3_RUNNING, type RoundSpec } from './round-mocks';

const liveUrl = 'http://127.0.0.1:22122';

const taskUrl = (suffix = '') => `${liveUrl}/#/task/demo/ship-report${suffix}`;

const hasNoSidewaysScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

const overviewRow = (page: Page, round: number) => page.locator(`[data-testid=round-overview-row][data-round="${round}"]`);

const roundToggle = (page: Page, round: number) => page.locator(`[data-testid=round-toggle][data-round="${round}"]`);

test.describe('review round overview', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    await mockRounds(page, [ROUND_1, ROUND_2, ROUND_3_RUNNING]);
  });

  test('opens from the file list: title, verdict, sentence, reviewer cards and findings of the round', async ({ page }) => {
    await page.goto(taskUrl());

    await expect(page.getByTestId('task-title')).toBeVisible();

    await expect(page.getByTestId('round-overview')).toBeHidden();

    await roundToggle(page, 1).click();

    await overviewRow(page, 1).click();

    await expect(page).toHaveURL(/#\/task\/demo\/ship-report\/round\/1$/);

    await expect(page.getByTestId('round-title')).toHaveText('Round 1');

    await expect(page.getByTestId('round-status')).toHaveText(/CHANGES/);

    await expect(page.getByTestId('round-summary')).toHaveText('2 of 3 reviewers asked for changes · 3 important findings, 6 nits · 1 note');

    await expect(page.getByTestId('reviewer-card')).toHaveCount(3);

    await expect(page.getByTestId('reviewer-card').nth(0).getByTestId('reviewer-counts')).toHaveText('2 important · 3 nits · opus');

    await expect(page.getByTestId('reviewer-card').nth(1).getByTestId('reviewer-counts')).toHaveText('0 important · 2 nits · opus');

    await expect(page.getByTestId('reviewer-card').nth(2).getByTestId('reviewer-counts')).toHaveText('1 important · 1 nit');

    await expect(page.getByTestId('reviewer-card').nth(2).getByTestId('reviewer-other')).toHaveText('Also holds text that is not a finding: shown below the findings.');

    await expect(page.getByTestId('reviewer-notes')).toHaveCount(1);

    await expect(page.getByTestId('reviewer-notes').locator('h3')).toHaveText('Notes from compliance');

    await expect(page.getByTestId('reviewer-notes').locator('strong')).toHaveText('pins');

    await expect(page.getByTestId('finding').last()).toContainText('Notes: src/AGENTS.md');

    await expect(page.getByTestId('finding')).toHaveCount(9);

    const severities = await page.getByTestId('finding').evaluateAll((cards) => cards.map((card) => card.getAttribute('data-severity')));

    expect(severities).toEqual(['important', 'important', 'important', 'nit', 'nit', 'nit', 'nit', 'nit', 'nit']);

    const first = page.getByTestId('finding').first();

    await expect(first.getByTestId('finding-location')).toHaveText('.git-flow/tests/guard.test.sh:6');

    await expect(first.getByTestId('finding-reviewer')).toHaveText('code');

    await expect(first.locator('dt:visible')).toHaveText(['What', 'Why', 'Fix']);

    await expect(first.locator('dd code').first()).toHaveText('git init');

    await expect(first.locator('dd strong')).toHaveText('real');

    await expect(first.locator('dd[data-kind=fix]')).toHaveCSS('background-color', 'rgb(227, 244, 232)');

    await expect(page.locator('main h1')).toHaveCount(1);
  });

  test('opens from a deep link, in a round the list shows closed, and an unknown round shows the first file', async ({ page }) => {
    await page.goto(taskUrl('/round/2'));

    await expect(page.getByTestId('round-title')).toHaveText('Round 2');

    await expect(page.getByTestId('round-status')).toHaveText(/PASS/);

    await expect(page.getByTestId('round-summary')).toHaveText('All 3 reviewers passed · 1 nit');

    await expect(overviewRow(page, 2)).toHaveAttribute('aria-current', 'true');

    // a link edited to a round that does not exist: the address goes back to the round that is shown
    await page.goto(taskUrl('/round/9'));

    await expect(page).toHaveURL(/\/round\/2$/);
  });

  test('shows the first file, with the address corrected, for a link to a round that does not exist', async ({ page }) => {
    await page.goto(taskUrl('/round/9'));

    await expect(page.getByTestId('reader-file')).toBeVisible();

    await expect(page.getByTestId('round-overview')).toBeHidden();

    await expect(page).not.toHaveURL(/round\/9/);
  });

  test('shows a running round with a spinner and the reviewers that have not reported', async ({ page }) => {
    await page.goto(taskUrl('/round/3'));

    await expect(page.getByTestId('round-status')).toHaveText(/RUNNING/);

    await expect(page.getByTestId('round-summary')).toHaveText('Of 3 reviewers: 1 passed, 2 not reported yet · 1 nit');

    const verdicts = page.getByTestId('reviewer-card').getByTestId('reviewer-verdict');

    await expect(verdicts).toHaveText([/RUNNING/, /PASS/, /RUNNING/]);

    await expect(page.locator('[data-testid=reviewer-card][data-reviewer=code]').getByTestId('reviewer-link')).toBeHidden();

    await expect(page.getByTestId('finding')).toHaveCount(1);

    const spinner = page.getByTestId('round-status').locator('.icon');

    await expect(spinner).not.toHaveCSS('animation-name', 'none');

    await page.emulateMedia({ reducedMotion: 'reduce' });

    await expect(spinner).toHaveCSS('animation-name', 'none');
  });

  test('marks the request of the human, whose file is the only one the round has', async ({ page }) => {
    await page.unroute('**/api/tasks/demo/ship-report');

    await mockRounds(page, [ROUND_1, ROUND_2, ROUND_3_HUMAN]);

    await page.goto(taskUrl('/round/3'));

    await expect(page.getByTestId('round-summary')).toHaveText('The reviewers have not reported yet · 2 important findings · includes a request from the human');

    const human = page.locator('[data-testid=reviewer-card][data-reviewer=human]');

    await expect(human.getByTestId('reviewer-origin')).toContainText('from the human');

    await expect(human.getByTestId('reviewer-link')).toBeVisible();

    await expect(page.getByTestId('finding')).toHaveCount(2);

    await expect(page.getByTestId('finding').first().locator('li')).toHaveCount(2);

    await expect(page.getByTestId('finding').first().getByTestId('finding-reviewer')).toHaveText('human');
  });

  test('switches rounds with the dropdown by mouse and keeps its width whatever the number of rounds', async ({ page }) => {
    await page.goto(taskUrl('/round/1'));

    const picker = page.getByTestId('round-picker');

    await expect(picker).toContainText('Round 1');

    const width = (await picker.boundingBox())!.width;

    await picker.click();

    await expect(picker).toHaveAttribute('aria-expanded', 'true');

    await expect(page.getByTestId('round-option')).toHaveCount(3);

    await expect(page.getByTestId('round-option').nth(0)).toHaveAttribute('aria-selected', 'true');

    await expect(page.getByTestId('round-option')).toContainText(['CHANGES', 'PASS', 'RUNNING']);

    await expect(page.getByTestId('round-option').nth(0)).toBeFocused();

    await page.getByTestId('round-option').nth(1).click();

    await expect(page.getByTestId('round-title')).toHaveText('Round 2');

    await expect(page).toHaveURL(/\/round\/2$/);

    await expect(page.getByTestId('round-menu')).toBeHidden();

    await expect(picker).toBeFocused();

    expect((await picker.boundingBox())!.width).toBe(width);

    await page.getByTestId('task-title').click();

    await picker.click();

    await expect(page.getByTestId('round-menu')).toBeVisible();

    await page.getByTestId('task-title').click();

    await expect(page.getByTestId('round-menu')).toBeHidden();
  });

  test('switches rounds with the keyboard: arrows move, Enter and Space pick, Escape closes and refocuses', async ({ page }) => {
    await page.goto(taskUrl('/round/1'));

    const picker = page.getByTestId('round-picker');

    await picker.focus();

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('round-option').nth(0)).toBeFocused();

    await page.keyboard.press('ArrowDown');

    await page.keyboard.press('ArrowDown');

    await expect(page.getByTestId('round-option').nth(2)).toBeFocused();

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('round-title')).toHaveText('Round 3');

    await expect(picker).toBeFocused();

    await page.keyboard.press('Space');

    await expect(page.getByTestId('round-option').nth(2)).toBeFocused();

    await page.keyboard.press('ArrowUp');

    await page.keyboard.press('Escape');

    await expect(page.getByTestId('round-menu')).toBeHidden();

    await expect(picker).toBeFocused();

    await expect(page.getByTestId('round-title')).toHaveText('Round 3');

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('round-option').nth(2)).toBeFocused();

    await page.keyboard.press('ArrowUp');

    await expect(page.getByTestId('round-option').nth(1)).toBeFocused();

    await page.keyboard.press('Space');

    await expect(page.getByTestId('round-title')).toHaveText('Round 2');
  });

  test('filters the findings with the chips and resets the filter when the round changes', async ({ page }) => {
    await page.goto(taskUrl('/round/1'));

    const chips = page.getByTestId('filter-chip');

    await expect(chips).toHaveText(['All 9', 'Important 3', 'Nits 6']);

    await expect(chips.nth(0)).toHaveAttribute('aria-pressed', 'true');

    await chips.nth(1).click();

    await expect(page.getByTestId('finding')).toHaveCount(3);

    await expect(chips.nth(1)).toHaveAttribute('aria-pressed', 'true');

    await expect(chips.nth(1)).toHaveCSS('background-color', 'rgb(21, 24, 36)');

    await chips.nth(2).click();

    await expect(page.getByTestId('finding')).toHaveCount(6);

    await page.getByTestId('round-picker').click();

    await page.getByTestId('round-option').nth(1).click();

    await expect(chips.nth(0)).toHaveAttribute('aria-pressed', 'true');

    await chips.nth(1).click();

    await expect(page.getByTestId('finding')).toHaveCount(0);

    await expect(page.getByTestId('findings-empty')).toHaveText('No important finding in this round.');
  });

  test('links a reviewer card to its file in the reader, and Back returns to the overview', async ({ page }) => {
    await page.goto(taskUrl('/round/1'));

    await page.locator('[data-testid=reviewer-card][data-reviewer=security]').getByTestId('reviewer-link').click();

    await expect(page).toHaveURL(new RegExp(`${encodeURIComponent(reviewPath(1, 'security')).replace(/[.]/g, '\\.')}$`));

    await expect(page.getByTestId('reader-file')).toHaveText('review-security.md');

    await expect(page.getByTestId('round-overview')).toBeHidden();

    await page.goBack();

    await expect(page.getByTestId('round-title')).toHaveText('Round 1');

    await expect(page.getByTestId('reviewer-card')).toHaveCount(3);

    await page.goForward();

    await expect(page.getByTestId('reader-file')).toHaveText('review-security.md');
  });

  test('keeps the filter and the page where they are when a poll brings the same round', async ({ page }) => {
    await page.goto(taskUrl('/round/1'));

    await page.getByTestId('filter-chip').nth(1).click();

    await expect(page.getByTestId('finding')).toHaveCount(3);

    await page.evaluate(() => window.scrollTo(0, 200));

    const marker = await page.getByTestId('finding').first().evaluate((element) => {
      element.setAttribute('data-kept', 'yes');

      return window.scrollY;
    });

    await page.waitForResponse((response) => response.url().endsWith('/api/board'), { timeout: 10_000 });

    await page.waitForTimeout(600);

    await expect(page.getByTestId('finding').first()).toHaveAttribute('data-kept', 'yes');

    await expect(page.getByTestId('finding')).toHaveCount(3);

    expect(await page.evaluate(() => window.scrollY)).toBe(marker);
  });

  test('stacks on a phone with the dropdown below the title and no sideways scroll, light and dark', async ({ page }) => {
    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });

      await page.setViewportSize({ width: 390, height: 844 });

      await page.goto(taskUrl('/round/1'));

      await page.reload();

      await expect(page.getByTestId('finding')).toHaveCount(9);

      expect(await hasNoSidewaysScroll(page)).toBe(true);

      const title = (await page.getByTestId('round-title').boundingBox())!;

      const picker = (await page.getByTestId('round-picker').boundingBox())!;

      expect(picker.y).toBeGreaterThan(title.y + title.height);

      await page.getByTestId('round-picker').click();

      const menu = (await page.getByTestId('round-menu').boundingBox())!;

      expect(menu.x).toBeGreaterThanOrEqual(0);

      expect(menu.x + menu.width).toBeLessThanOrEqual(390);

      const cardBoxes = await page.getByTestId('reviewer-card').evaluateAll((cards) => cards.map((card) => Math.round(card.getBoundingClientRect().left)));

      expect(new Set(cardBoxes).size).toBe(1);
    }
  });

  test('keeps the width of the dropdown for twelve rounds, and lists them in a menu that scrolls', async ({ page }) => {
    const width = async () => (await page.getByTestId('round-picker').boundingBox())!.width;

    await page.goto(taskUrl('/round/1'));

    const three = await width();

    await page.unroute('**/api/tasks/demo/ship-report');

    await mockRounds(page, Array.from({ length: 12 }, (_, index) => ({ ...ROUND_2, round: index + 1 })));

    await page.goto('about:blank');

    await page.goto(taskUrl('/round/12'));

    await expect(page.getByTestId('round-picker')).toContainText('Round 12');

    expect(await width()).toBe(three);

    await page.getByTestId('round-picker').click();

    await expect(page.getByTestId('round-option')).toHaveCount(12);

    const list = page.locator('#round-listbox');

    expect(await list.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  });

  test('scrolls a long code block or table inside its own box, in a finding and in the notes', async ({ page }) => {
    const wide = 'x'.repeat(400);

    const text = [
      'CHANGES long output',
      `- [Important] a.sh:1 - What: the log shows a long line:`,
      '```',
      `${wide} end`,
      '```',
      'Why: it hides the failure. Fix: wrap it.',
      '',
      'A table in the notes:',
      '',
      `| key | value |`,
      `| --- | --- |`,
      `| ${wide} | b |`,
      '',
      '```',
      `${wide} notes`,
      '```',
      '=== END OF REVIEW ===',
      '',
    ].join('\n');

    await page.unroute('**/api/tasks/demo/ship-report');

    await mockRounds(page, [{ round: 1, reviews: { code: 'CHANGES' }, texts: { code: text } }]);

    await page.goto(taskUrl('/round/1'));

    await expect(page.getByTestId('finding')).toHaveCount(1);

    for (const scope of [page.getByTestId('finding'), page.getByTestId('reviewer-notes')]) {
      const pre = scope.locator('pre').first();

      await expect(pre).toHaveCSS('overflow-x', 'auto');

      const box = await pre.evaluate((element) => ({ scroll: element.scrollWidth, client: element.clientWidth, right: element.getBoundingClientRect().right }));

      expect(box.scroll).toBeGreaterThan(box.client);

      const outer = (await scope.boundingBox())!;

      expect(box.right).toBeLessThanOrEqual(outer.x + outer.width);
    }

    const table = page.getByTestId('reviewer-notes').locator('table');

    await expect(table).toHaveCSS('overflow-x', 'auto');

    expect(await hasNoSidewaysScroll(page)).toBe(true);
  });

  test('takes a long unbreakable text without sideways scroll', async ({ page }) => {
    const long: RoundSpec = { round: 1, reviews: { code: 'CHANGES' }, texts: { code: `CHANGES ${'x'.repeat(200)}\n- [Important] ${'a/'.repeat(120)}file.ts:1 - What: ${'y'.repeat(300)} \`${'z'.repeat(200)}\`. Why: w. Fix: f.\n=== END OF REVIEW ===\n` } };

    await page.unroute('**/api/tasks/demo/ship-report');

    await mockRounds(page, [long]);

    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto(taskUrl('/round/1'));

    await expect(page.getByTestId('finding')).toHaveCount(1);

    expect(await hasNoSidewaysScroll(page)).toBe(true);
  });
});
