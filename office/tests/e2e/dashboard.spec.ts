import { expect, test, type Page } from '@playwright/test';

const columnNames = ['Backlog', 'Design', 'In progress', 'Ready for MR', 'In review', 'Done', 'Needs human'];
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
    await expect(page.locator('[data-column] h2 span:first-child')).toHaveText(columnNames);
    await expect(column(page, 'Backlog').locator('[data-task="demo/add-login"]')).toBeVisible();
    await expect(column(page, 'In progress').locator('[data-task="demo/fix-export"]')).toBeVisible();
    await expect(column(page, 'Done').locator('[data-task="demo/ship-report"]')).toBeVisible();
    await expect(column(page, 'Design').getByText('No tasks')).toBeVisible();
  });

  test('lists the active agent and marks its card', async ({ page }) => {
    await expect(page.getByTestId('agent-item')).toContainText('argani:builder');
    await expect(page.getByTestId('agent-item')).toContainText('demo/fix-export');
    await expect(taskCard(page, 'demo/fix-export').getByTestId('agent-marker')).toBeVisible();
    await expect(taskCard(page, 'demo/add-login').getByTestId('agent-marker')).toBeHidden();
  });

  test('filters by project', async ({ page }) => {
    await page.getByTestId('project-filter').selectOption('demo');
    await expect(page.locator('.card')).toHaveCount(3);
    await page.getByTestId('project-filter').selectOption('other');
    await expect(page.locator('.card')).toHaveCount(1);
    await page.getByTestId('project-filter').selectOption('');
    await expect(page.locator('.card')).toHaveCount(4);
  });

  test('keeps the old data and shows a banner when the backend starts failing', async ({ page }) => {
    await page.route('**/api/board', (route) => route.fulfill({ status: 500, json: { error: 'board unreadable' } }));
    await expect(page.getByTestId('error-banner')).toContainText('board unreadable', { timeout: 15_000 });
    await expect(page.getByTestId('status')).toHaveText('Disconnected');
    await expect(page.locator('.card')).toHaveCount(4);
  });
});

test('shows a banner and no data when the backend is unreachable', async ({ page }) => {
  await page.goto(deadBackendUrl);
  await expect(page.getByTestId('error-banner')).toBeVisible();
  await expect(page.getByTestId('status')).toHaveText('Disconnected');
  await expect(page.locator('.card')).toHaveCount(0);
});
