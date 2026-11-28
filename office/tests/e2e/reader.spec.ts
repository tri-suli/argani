import { expect, test, type Page } from '@playwright/test';
import { DECISION_DOCUMENT, DESCRIPTION_DOCUMENT, DIFF_DOCUMENT, INTENT_DOCUMENT, REVIEW_DOCUMENT, SPEC_DOCUMENT } from './reader-documents';

const liveUrl = 'http://127.0.0.1:22122';

const taskUrl = (path: string) => `${liveUrl}/#/task/demo/ship-report/${encodeURIComponent(path)}`;

/** Serves `text` for a file of the task instead of the fixture file. */
async function serveFile(page: Page, path: string, text: string) {
  await page.route(`**/api/tasks/demo/ship-report/file?path=${encodeURIComponent(path)}`, (route) => route.fulfill({ body: text, contentType: 'text/plain' }));
}

/** Lists one more file in the task, for a document the fixture home does not have. */
async function listFile(page: Page, path: string) {
  await page.route('**/api/tasks/demo/ship-report', async (route) => {
    const task = await (await route.fetch()).json();

    task.files.unshift({ path, group: 'Job', firstLine: '', tone: null });

    await route.fulfill({ json: task });
  });
}

const hasNoSidewaysScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test.describe('document reader', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    await serveFile(page, 'spec.md', SPEC_DOCUMENT);
  });

  test('reads a spec: head, meta strip, summary, body, criteria cards and the outline count', async ({ page }) => {
    await page.goto(taskUrl('spec.md'));

    await expect(page.getByTestId('reader-file')).toHaveText('spec.md');

    await expect(page.getByTestId('task-verdict')).toHaveText('approved by argani');

    await expect(page.getByTestId('reader-title')).toContainText('Spec: Install Laravel in src/ with the project check');

    await expect(page.getByTestId('reader-title').locator('code')).toHaveText('src/');

    await expect(page.getByTestId('meta-entry')).toHaveText([/Intent\s*install-laravel-in-src/, /Status\s*approved by argani on 2026-11-26/, /Date\s*2026-11-26/]);

    await expect(page.getByTestId('task-summary')).toContainText('Install the Laravel 13 skeleton');

    await expect(page.getByTestId('task-body').locator('h3').first()).toHaveText('Approach');

    await expect(page.getByTestId('task-body').locator('h3').first()).toHaveCSS('font-size', '21px');

    await expect(page.getByTestId('task-body').locator('blockquote')).toBeVisible();

    await expect(page.getByTestId('task-body').locator('table')).toBeVisible();

    await expect(page.getByTestId('criterion')).toHaveCount(5);

    const manual = page.getByTestId('criterion').nth(3);

    await expect(manual.getByTestId('criterion-id')).toHaveText('AC-4');

    await expect(manual.getByTestId('criterion-manual')).toContainText('manual');

    await expect(manual.getByTestId('criterion-verify')).toHaveCount(0);

    const automatic = page.getByTestId('criterion').first();

    await expect(automatic.getByTestId('criterion-verify')).toContainText('docker compose up -d --wait');

    await expect(automatic.getByTestId('criterion-verify')).toHaveCSS('font-family', /IBM Plex Mono/);

    await expect(page.getByTestId('outline-entry').filter({ hasText: 'Acceptance criteria' }).first().getByTestId('outline-count')).toHaveText('5');

    await expect(page.getByTestId('reader-stats')).toHaveText(/\d[\d,]* words · \d+ min read/);
  });

  test('scrolls to a section from the outline and keeps the route; the highlight follows the scroll', async ({ page }) => {
    await page.goto(taskUrl('spec.md'));

    const route = page.url();

    const entries = page.getByTestId('outline-entry');

    await expect(entries.first()).toHaveAttribute('aria-current', 'location');

    await entries.filter({ hasText: 'Out of scope' }).click();

    await expect(page.locator('#doc-out-of-scope')).toBeInViewport();

    await expect(entries.filter({ hasText: 'Out of scope' })).toHaveAttribute('aria-current', 'location');

    expect(page.url()).toBe(route);

    await expect(page.getByTestId('task-page')).toBeVisible();

    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));

    await expect(entries.first()).toHaveAttribute('aria-current', 'location');

    await page.locator('#doc-flagged-concerns').scrollIntoViewIfNeeded();

    await page.evaluate(() => document.getElementById('doc-flagged-concerns')?.scrollIntoView({ behavior: 'instant', block: 'start' }));

    await expect(entries.filter({ hasText: 'Flagged concerns' })).toHaveAttribute('aria-current', 'location');

    expect(page.url()).toBe(route);
  });

  test('lets go of the last section after a click when it is too short to reach the zone, and follows the End key', async ({ page }) => {
    await page.goto(taskUrl('spec.md'));

    const entries = page.getByTestId('outline-entry');

    await entries.last().click();

    await expect(entries.last()).toHaveAttribute('aria-current', 'location');

    await expect(page.locator('#doc-out-of-scope')).toBeFocused();

    // the click scrolls smoothly: scrolling back before it arrived would be undone by the rest of that scroll
    await expect.poll(() => page.evaluate(() => window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2)).toBe(true);

    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));

    await expect(entries.first()).toHaveAttribute('aria-current', 'location');

    await page.keyboard.press('End');

    await expect(page.locator('[data-testid=outline-entry][aria-current=location]')).toHaveText(/Open questions|Out of scope/);

    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));

    await expect(entries.first()).toHaveAttribute('aria-current', 'location');
  });

  test('jumps instantly under reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });

    await page.goto(taskUrl('spec.md'));

    await page.getByTestId('outline-entry').filter({ hasText: 'Out of scope' }).click();

    const scrollRightAfter = await page.evaluate(() => window.scrollY);

    await page.waitForTimeout(800);

    expect(scrollRightAfter).toBeGreaterThan(0);

    expect(await page.evaluate(() => window.scrollY)).toBe(scrollRightAfter);
  });

  test('follows an in-document link of the markdown without leaving the task', async ({ page }) => {
    await page.goto(taskUrl('spec.md'));

    const route = page.url();

    await page.getByTestId('task-summary').getByRole('link', { name: 'the approach' }).click();

    await expect(page.locator('#doc-approach')).toBeInViewport();

    expect(page.url()).toBe(route);

    await expect(page.getByTestId('task-page')).toBeVisible();
  });

  test('opens other links in a new tab safely', async ({ page }) => {
    await page.goto(taskUrl('spec.md'));

    const link = page.getByRole('link', { name: 'Laravel docs' });

    await expect(link).toHaveAttribute('target', '_blank');

    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  test('copies a code block, says Copied for a moment, and shows the language', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);

    await page.goto(taskUrl('spec.md'));

    const block = page.getByTestId('code-block').first();

    await expect(block.getByTestId('code-language')).toHaveText('bash');

    const copy = block.getByRole('button', { name: 'Copy code' });

    await expect(copy).toHaveText('Copy');

    await copy.click();

    await expect(copy).toHaveText('Copied');

    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('git rebase --exec "npm run check" origin/develop');

    await expect(copy).toHaveText('Copy');
  });

  test('keeps the page free of sideways scrolling on a phone, with the outline below the document, in light and dark', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });

      await page.goto(taskUrl('spec.md'));

      await expect(page.getByTestId('reader-title')).toBeVisible();

      expect(await hasNoSidewaysScroll(page)).toBe(true);

      const article = (await page.getByRole('article', { name: 'Document' }).boundingBox())!;

      const outline = (await page.getByTestId('reader-outline').boundingBox())!;

      expect(outline.y).toBeGreaterThanOrEqual(article.y + article.height);

      const table = page.getByTestId('task-body').locator('table');

      expect(await table.evaluate((element) => getComputedStyle(element).overflowX)).toBe('auto');

      const copy = (await page.getByTestId('code-copy').first().boundingBox())!;

      expect(copy.height).toBeGreaterThanOrEqual(44);

      await page.goto(liveUrl);
    }
  });

  test('draws the callout and the code block with their own tokens in light and dark', async ({ page }) => {
    await page.goto(taskUrl('spec.md'));

    const colours = () => page.evaluate(() => [getComputedStyle(document.querySelector('[data-testid=task-summary]')!).backgroundColor, getComputedStyle(document.querySelector('[data-testid=code-block] pre')!).backgroundColor]);

    await page.emulateMedia({ colorScheme: 'light' });

    expect(await colours()).toEqual(['rgb(243, 245, 254)', 'rgb(21, 24, 36)']);

    await page.emulateMedia({ colorScheme: 'dark' });

    expect(await colours()).toEqual(['rgb(35, 40, 66)', 'rgb(13, 14, 19)']);
  });

  test('reads intent criteria with the verify command in the chip, and a decision with its round', async ({ page }) => {
    await serveFile(page, 'intent.md', INTENT_DOCUMENT);

    await serveFile(page, 'decision.md', DECISION_DOCUMENT);

    await page.goto(taskUrl('intent.md'));

    await expect(page.getByTestId('criterion')).toHaveCount(2);

    await expect(page.getByTestId('criterion').first().getByTestId('criterion-verify')).toContainText('docker compose config --services');

    await expect(page.getByTestId('criterion').nth(1).getByTestId('criterion-manual')).toContainText('docker compose up -d --build --wait');

    await expect(page.getByTestId('meta-entry')).toHaveCount(4);

    await page.goto(taskUrl('decision.md'));

    await expect(page.getByTestId('task-verdict')).toContainText('APPROVE');

    await expect(page.getByTestId('meta-entry')).toHaveText([/Round\s*1/]);
  });

  test('shows a real description.md as text under its file name, not as a meta cell', async ({ page }) => {
    await serveFile(page, 'description.md', DESCRIPTION_DOCUMENT);

    await listFile(page, 'description.md');

    await page.goto(taskUrl('description.md'));

    await expect(page.getByTestId('task-body')).toContainText('DOCKER STABLE STACK: setup Docker dengan tiga layanan');

    await expect(page.getByTestId('task-meta')).toBeHidden();

    await expect(page.getByTestId('task-status')).toBeHidden();
  });

  test('reads a review file with the same reader', async ({ page }) => {
    await serveFile(page, 'review/round-1/review-code.md', REVIEW_DOCUMENT);

    await page.goto(taskUrl('review/round-1/review-code.md'));

    await expect(page.getByTestId('task-verdict')).toContainText('CHANGES one Important finding');

    await expect(page.getByTestId('task-summary')).toContainText('The four pins match spec.md');

    await expect(page.getByTestId('task-body')).toContainText('compose.yaml:122');
  });
});

test.describe('diff reader', () => {
  test.beforeEach(async ({ page }) => {
    await serveFile(page, 'review/round-1/change.diff', DIFF_DOCUMENT);
  });

  test('tells added, removed, hunk and file lines apart by colour and marker, separates files and scrolls long lines inside its box', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto(taskUrl('review/round-1/change.diff'));

    const rows = page.getByTestId('diff-row');

    await expect(rows.first()).toContainText('diff --git a/compose.yaml');

    const add = rows.filter({ hasText: '+    image: nginx:1.30-alpine' });

    const remove = rows.filter({ hasText: '-    image: nginx:1.31-alpine' });

    await expect(add).toHaveAttribute('data-kind', 'add');

    await expect(remove).toHaveAttribute('data-kind', 'remove');

    await expect(add).toHaveText(/^\+/);

    await expect(remove).toHaveText(/^-/);

    await expect(rows.filter({ hasText: '@@ -102,7' })).toHaveAttribute('data-kind', 'hunk');

    await expect(rows.filter({ hasText: 'Binary files' })).toHaveAttribute('data-kind', 'binary');

    expect(await add.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe(await remove.evaluate((element) => getComputedStyle(element).backgroundColor));

    await expect(page.locator('[data-testid=diff-row][data-start=true]')).toHaveCount(3);

    expect(await hasNoSidewaysScroll(page)).toBe(true);

    const scroller = page.getByRole('region', { name: 'Diff' });

    expect(await scroller.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);

    await expect(page.getByTestId('diff-note')).toBeHidden();
  });

  test('stays responsive on a huge diff and names how much it shows', async ({ page }) => {
    await serveFile(page, 'review/round-1/change.diff', Array.from({ length: 30000 }, (_, index) => `+line ${index}`).join('\n'));

    await page.goto(taskUrl('review/round-1/change.diff'));

    await expect(page.getByTestId('diff-note')).toHaveText('Showing the first 1,500 lines of 30,000.');

    await expect(page.getByTestId('diff-row')).toHaveCount(1500);
  });

  test('has no sideways page scroll on a phone, in light and dark', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });

      await page.goto(taskUrl('review/round-1/change.diff'));

      await expect(page.getByTestId('diff-row').first()).toBeVisible();

      expect(await hasNoSidewaysScroll(page)).toBe(true);

      await page.goto(liveUrl);
    }
  });
});
