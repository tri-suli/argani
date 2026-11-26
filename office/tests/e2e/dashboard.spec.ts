import { expect, test, type Page } from '@playwright/test';

const columnNames = ['Intake', 'Spec', 'Build', 'Review', 'Approve', 'Needs human', 'Done'];

const liveUrl = 'http://127.0.0.1:22122';

const deadBackendUrl = 'http://127.0.0.1:22123';

const taskCard = (page: Page, task: string) => page.locator(`[data-task="${task}"]`);

const column = (page: Page, name: string) => page.locator(`[data-column="${name}"]`);

test.describe('with a live backend', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(liveUrl);

    await expect(page.getByTestId('status')).toHaveText('Connected');
  });

  test('shows all seven columns with the fixture tasks in the right ones', async ({ page }) => {
    await expect(page.locator('[data-column]')).toHaveCount(7);

    await expect(page.locator('[data-column] h2')).toHaveText(columnNames);

    await expect(column(page, 'Intake').locator('[data-task="demo/add-login"]')).toBeVisible();

    await expect(column(page, 'Intake').locator('[data-task="other/write-docs"]')).toBeVisible();

    await expect(taskCard(page, 'demo/add-login').getByTestId('card-flag')).toBeHidden();

    await expect(column(page, 'Build').locator('[data-task="demo/fix-export"]')).toBeVisible();

    await expect(column(page, 'Done').locator('[data-task="demo/ship-report"]')).toBeVisible();

    await expect(column(page, 'Spec').getByText('No tasks')).toBeVisible();
  });

  test('shows the question, reason and badge on the Needs human card from board.json', async ({ page }) => {
    const card = taskCard(page, 'demo/pick-database');

    await expect(column(page, 'Needs human').locator('[data-task="demo/pick-database"]')).toBeVisible();

    await expect(card.getByTestId('card-flag')).toHaveText('intake-question');

    await expect(card.getByTestId('card-hint')).toHaveText('Which database should the report use?');

    await expect(card.getByTestId('card-badge')).toHaveText('2× you');

    await expect(taskCard(page, 'demo/add-login').getByTestId('card-hint')).toBeHidden();
  });

  test('shows manual criteria and waiting time in the footer totals', async ({ page }) => {
    await expect(page.getByTestId('totals')).toContainText('1 manual ACs');

    await expect(page.getByTestId('totals')).toContainText('waiting for you');
  });

  test('lists the column history and metrics of a task in the drawer', async ({ page }) => {
    await taskCard(page, 'demo/pick-database').click();

    const rows = page.getByTestId('history-row');

    await expect(rows).toHaveCount(4);

    await expect(rows.nth(0)).toHaveText('Intake30m');

    await expect(rows.nth(1)).toHaveText('Needs human1h00m');

    await expect(rows.nth(2)).toHaveText('Intake15m');

    await expect(rows.nth(3)).toContainText('Needs human');

    await expect(page.getByTestId('drawer-metrics')).toContainText('1 manual ACs');

    await expect(page.getByTestId('drawer-metrics')).toContainText('2× in Needs human');
  });

  test('shows a dash for a task without history in the drawer', async ({ page }) => {
    await taskCard(page, 'demo/add-login').click();

    await expect(page.getByTestId('history-empty')).toHaveText('—');

    await expect(page.getByTestId('history-row')).toHaveCount(0);
  });

  test('lays the seven columns out left to right in one row, Needs human before Done', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const boxes = await Promise.all(columnNames.map((name) => column(page, name).boundingBox()));

    const rects = boxes.map((box) => box!);

    rects.forEach((box, index) => {
      expect(box.y).toBeCloseTo(rects[0].y, 0);

      if (index > 0) {
        expect(box.x).toBeGreaterThanOrEqual(rects[index - 1].x + rects[index - 1].width);
      }
    });

    expect(rects[6].width).toBeGreaterThan(150);
  });

  test('shows agent time and tokens on the finished task card', async ({ page }) => {
    const card = taskCard(page, 'demo/ship-report');

    await expect(card.getByTestId('card-time')).toHaveText('2m');

    await expect(card.getByTestId('card-tokens')).toHaveText('6.0k tok');

    await expect(card.getByTestId('card-risk')).toHaveText('medium');

    await expect(card.locator('a', { hasText: 'MR' })).toHaveAttribute('href', 'https://example.com/demo/merge_requests/1');

    await expect(card.locator('.round')).toHaveCount(2);

    await expect(page.getByTestId('totals')).toContainText('1 agents running · 6.0k tokens');
  });

  test('opens the drawer from a card, lists its files, renders one and closes with Escape', async ({ page }) => {
    const card = taskCard(page, 'demo/ship-report');

    await card.click();

    const drawer = page.getByTestId('drawer');

    await expect(drawer).toBeVisible();

    await expect(page.getByRole('dialog')).toBeVisible();

    await expect(page.getByTestId('drawer-headline')).toContainText('demo · ship-report');

    await expect(page.getByTestId('drawer-headline')).toContainText('6.0k tok');

    await expect(drawer.locator('[data-testid=file-group]')).toHaveText(['Job', 'Round 1', 'Round 2']);

    await expect(drawer.locator('.file').first()).toHaveText('intent.md');

    await expect(page.getByTestId('drawer-body').locator('h1')).toHaveText('Intent: Ship report');

    await drawer.locator('.file', { hasText: 'review-code.md' }).first().click();

    await expect(page.getByTestId('drawer-verdict')).toHaveText('CHANGES missing a test');

    await drawer.locator('.file', { hasText: 'change.diff' }).first().click();

    await expect(page.getByTestId('drawer-plain')).toContainText('diff --git');

    await page.keyboard.press('Escape');

    await expect(drawer).toBeHidden();

    await expect(card).toBeFocused();
  });

  test('marks the card of the active agent', async ({ page }) => {
    await expect(page.getByTestId('totals')).toContainText('1 agents running');

    await expect(taskCard(page, 'demo/fix-export').getByTestId('agent-marker')).toBeVisible();

    await expect(taskCard(page, 'demo/add-login').getByTestId('agent-marker')).toBeHidden();
  });

  test('filters by project', async ({ page }) => {
    await page.getByTestId('project-filter').selectOption('demo');

    await expect(page.locator(".card")).toHaveCount(4);

    await page.getByTestId('project-filter').selectOption('other');

    await expect(page.locator('.card')).toHaveCount(1);

    await page.getByTestId('project-filter').selectOption('');

    await expect(page.locator('.card')).toHaveCount(5);
  });

  test('keeps the old data and shows a banner when the backend starts failing', async ({ page }) => {
    await page.route('**/api/board', (route) => route.fulfill({ status: 500, json: { error: 'board unreadable' } }));

    await expect(page.getByTestId('error-banner')).toContainText('board unreadable', { timeout: 15_000 });

    await expect(page.getByTestId('status')).toHaveText('Disconnected');

    await expect(page.locator('.card')).toHaveCount(5);
  });
});

test('shows a banner and no data when the backend is unreachable', async ({ page }) => {
  await page.goto(deadBackendUrl);

  await expect(page.getByTestId('error-banner')).toBeVisible();

  await expect(page.getByTestId('status')).toHaveText('Disconnected');

  await expect(page.locator('.card')).toHaveCount(0);
});
