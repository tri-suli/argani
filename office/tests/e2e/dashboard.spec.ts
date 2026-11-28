import { expect, test, type Page } from '@playwright/test';

const columnNames = ['Intake', 'Spec', 'Build', 'Review', 'Approve'];

const liveUrl = 'http://127.0.0.1:22122';

const deadBackendUrl = 'http://127.0.0.1:22123';

const minimumTouchTarget = 44;

const taskCard = (page: Page, task: string) => page.locator(`[data-task="${task}"]`);

const column = (page: Page, name: string) => page.locator(`[data-column="${name}"]`);

const tile = (page: Page, id: string) => page.locator(`[data-tile="${id}"]`);

/** Serves the live board with `change` applied to its JSON, to show states the fixture home does not have. */
async function changeBoard(page: Page, change: (board: { projects: { tasks: Record<string, unknown>[] }[] }) => void) {
  await page.route('**/api/board', async (route) => {
    const board = await (await route.fetch()).json();

    change(board);

    await route.fulfill({ json: board });
  });
}

const findTask = (board: { projects: { tasks: Record<string, unknown>[] }[] }, slug: string) => board.projects.flatMap((project) => project.tasks).find((task) => task.slug === slug)!;

test.describe('with a live backend', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(liveUrl);

    await expect(page.getByTestId('status')).toHaveText('Connected');
  });

  test('has the title, the header and the bundled fonts, with every icon drawn as a glyph', async ({ page }) => {
    await expect(page).toHaveTitle('Argani Office');

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Argani Office');

    const fonts = await page.evaluate(async () => {
      await document.fonts.ready;

      return { sans: document.fonts.check('14px "IBM Plex Sans"'), mono: document.fonts.check('12px "IBM Plex Mono"'), icons: document.fonts.check('18px "Material Symbols Outlined"') };
    });

    expect(fonts).toEqual({ sans: true, mono: true, icons: true });

    // a ligature that did not load would show its name ("folder_open") as a word, far wider than a glyph
    const widths = await page.locator('.icon').evaluateAll((icons) => icons.filter((icon) => icon.getBoundingClientRect().width > 0).map((icon) => icon.getBoundingClientRect().width));

    expect(widths.length).toBeGreaterThan(0);

    expect(Math.max(...widths)).toBeLessThan(30);
  });

  test('shows the five pipeline columns, numbered, with a count badge and the agent names on the badge', async ({ page }) => {
    await expect(page.locator('[data-column]')).toHaveCount(5);

    await expect(page.locator('[data-column] h2')).toHaveText(columnNames);

    await expect(page.getByTestId('column-step')).toHaveText(['01', '02', '03', '04', '05']);

    await expect(page.getByTestId('column-count')).toHaveText(['2', '0', '1', '0', '0']);

    await expect(page.getByTestId('column-count').nth(2)).toHaveAttribute('title', 'builder · verify');

    await expect(column(page, 'Intake').locator('[data-task="demo/add-login"]')).toBeVisible();

    await expect(column(page, 'Intake').locator('[data-task="other/write-docs"]')).toBeVisible();

    await expect(column(page, 'Build').locator('[data-task="demo/fix-export"]')).toBeVisible();

    await expect(column(page, 'Spec').getByText('Nothing here')).toBeVisible();

    await expect(page.locator('footer')).toHaveCount(0);
  });

  test('shows the four totals tiles', async ({ page }) => {
    await expect(tile(page, 'agents')).toContainText('Agents working');

    await expect(tile(page, 'agents').getByTestId('tile-value')).toHaveText('1');

    await expect(tile(page, 'agents').getByTestId('tile-detail')).toHaveText('builder');

    await expect(tile(page, 'waiting').getByTestId('tile-value')).toHaveText(/^\d+h\d\dm$|^\d+m$/);

    await expect(tile(page, 'waiting').getByTestId('tile-detail')).toHaveText('1 task');

    await expect(tile(page, 'tokens').getByTestId('tile-value')).toHaveText('0');

    await expect(tile(page, 'tokens').getByTestId('tile-detail')).toHaveText('across 4 open tasks');

    await expect(tile(page, 'manual').getByTestId('tile-value')).toHaveText('1');
  });

  test('lists the task in Needs human with its reason, wait, visits, question and answer command', async ({ page }) => {
    const row = page.locator('[data-row="demo/pick-database"]');

    await expect(page.getByTestId('needs-human-count')).toHaveText('1');

    await expect(row.getByTestId('row-project')).toHaveText('demo');

    await expect(row.getByTestId('row-reason')).toHaveText('intake question');

    await expect(row.getByTestId('row-waiting')).toContainText('waiting');

    await expect(row.getByTestId('row-visits')).toContainText('2× you');

    await expect(row.getByTestId('row-title')).toHaveText(/./);

    await expect(row.getByTestId('row-question')).toHaveText('Which database should the report use?');

    await expect(row.getByTestId('row-command')).toHaveText('/argani:factory answer pick-database <answer>');
  });

  test('copies the answer command to the clipboard and says Copied for a moment', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);

    const copy = page.locator('[data-row="demo/pick-database"]').getByTestId('row-copy');

    await expect(copy).toHaveText('Copy');

    await copy.click();

    await expect(copy).toHaveText('Copied');

    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('/argani:factory answer pick-database <answer>');

    await expect(copy).toHaveText('Copy', { timeout: 5000 });
  });

  test('orders the Needs human rows by the longest wait first and keeps the message of an unreadable task', async ({ page }) => {
    await changeBoard(page, (board) => {
      const [project] = board.projects;

      const ask = (slug: string, since: string, question: string | null) => ({
        ...findTask(board, 'fix-export'),
        slug,
        title: `Task ${slug}`,
        column: 'Needs human',
        reason: 'manual-verification',
        question,
        history: [{ ts: since, stage: 'needs-human', column: 'Needs human', reason: 'manual-verification' }],
      });

      project.tasks.push(ask('longest', '2026-01-01T00:00:00Z', 'The oldest question?'), ask('newest', new Date(Date.now() - 60_000).toISOString(), 'The newest question?'));

      project.tasks.push({ ...ask('broken', '2026-01-01T00:00:00Z', 'tasks.json is unreadable'), column: 'Unreadable', history: [] });
    });

    await page.reload();

    await expect(page.getByTestId('needs-human-count')).toHaveText('4');

    await expect(page.getByTestId('needs-human-row')).toHaveCount(4);

    const order = await page.getByTestId('needs-human-row').evaluateAll((rows) => rows.map((row) => row.getAttribute('data-row')));

    expect(order[0]).toBe('demo/longest');

    expect(order.at(-1)).toBe('demo/broken');

    expect(order.indexOf('demo/newest')).toBeLessThan(order.indexOf('demo/broken'));

    await expect(page.locator('[data-row="demo/broken"]').getByTestId('row-question')).toHaveText('tasks.json is unreadable');
  });

  test('lists the finished task in the Done rail as merged, with its agent time', async ({ page }) => {
    await expect(page.getByTestId('done-count')).toHaveText('1');

    const row = page.getByTestId('done-row');

    await expect(row.getByTestId('done-title')).toHaveText(/./);

    await expect(row.getByTestId('done-outcome')).toHaveText('merge merged');

    await expect(row.getByTestId('done-time')).toHaveText('· 2m');

    await expect(page.getByTestId('done-title')).toHaveCSS('text-decoration-line', 'none');
  });

  test('shows a cancelled task struck through in the Done rail, ahead of an older merged one', async ({ page }) => {
    await changeBoard(page, (board) => {
      Object.assign(findTask(board, 'write-docs'), { column: 'Done', stage: 'cancelled' });
    });

    await page.reload();

    await expect(page.getByTestId('done-count')).toHaveText('2');

    const cancelled = page.locator('[data-testid=done-row]', { hasText: 'cancelled' });

    await expect(cancelled.getByTestId('done-outcome')).toHaveText('block cancelled');

    await expect(cancelled.getByTestId('done-title')).toHaveCSS('text-decoration-line', 'line-through');
  });

  test('shows rounds, risk, agent time, tokens and the MR link on a card in Review', async ({ page }) => {
    await changeBoard(page, (board) => {
      Object.assign(findTask(board, 'ship-report'), { column: 'Review', stage: 'needs-review' });
    });

    await page.reload();

    const card = taskCard(page, 'demo/ship-report');

    await expect(column(page, 'Review').locator('.card')).toHaveCount(1);

    await expect(card.getByTestId('card-project')).toHaveText('demo');

    await expect(card.getByTestId('card-risk')).toHaveText('medium');

    await expect(card.getByTestId('card-time')).toHaveText('2m');

    await expect(card.getByTestId('card-tokens')).toHaveText('6.0k tok');

    await expect(card.locator('a', { hasText: 'MR' })).toHaveAttribute('href', 'https://example.com/demo/merge_requests/1');

    await expect(card.locator('.round')).toHaveCount(2);

    // PASS, CHANGES and the others differ by icon as well as colour
    await expect(card.locator('.round').first().locator('.chip').first()).toContainText('priority_high');

    await expect(card.locator('.round').last().locator('.chip').first()).toContainText('check');
  });

  test('shows the running agent and its elapsed time on the card it works on', async ({ page }) => {
    const card = taskCard(page, 'demo/fix-export');

    await expect(card).toHaveAttribute('data-active', 'true');

    await expect(card.getByTestId('card-working')).toContainText(/builder · \d+s|builder · \d+m/);

    await expect(taskCard(page, 'demo/add-login').getByTestId('card-working')).toHaveCount(0);
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

  test('lays the five columns out left to right in one row with the Done rail to their right', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const boxes = await Promise.all(columnNames.map((name) => column(page, name).boundingBox()));

    const rects = boxes.map((box) => box!);

    rects.forEach((box, index) => {
      expect(box.y).toBeCloseTo(rects[0].y, 0);

      if (index > 0) {
        expect(box.x).toBeGreaterThanOrEqual(rects[index - 1].x + rects[index - 1].width);
      }
    });

    const rail = (await page.getByTestId('done-rail').boundingBox())!;

    expect(rail.x).toBeGreaterThanOrEqual(rects[4].x + rects[4].width);

    expect(rail.y).toBeCloseTo(rects[0].y, -1);
  });

  test('stacks the columns and puts the Done rail below on a phone, without sideways scrolling', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    const boxes = await Promise.all(columnNames.map((name) => column(page, name).boundingBox()));

    boxes.forEach((box, index) => {
      if (index > 0) {
        expect(box!.y).toBeGreaterThan(boxes[index - 1]!.y);
      }

      expect(box!.x).toBeCloseTo(boxes[0]!.x, 0);
    });

    const rail = (await page.getByTestId('done-rail').boundingBox())!;

    expect(rail.y).toBeGreaterThan(boxes[4]!.y);

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
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

  test('opens the drawer from a pipeline card with the keyboard', async ({ page }) => {
    await taskCard(page, 'demo/fix-export').focus();

    await page.keyboard.press('Enter');

    await expect(page.getByRole('dialog')).toBeVisible();
  });
});

test.describe('the project picker', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(liveUrl);

    await expect(page.getByTestId('status')).toHaveText('Connected');
  });

  const picker = (page: Page) => page.getByTestId('project-picker');

  test('lists All projects and every project with their task counts and the tasks waiting for you', async ({ page }) => {
    await expect(picker(page)).toContainText('All projects');

    await expect(picker(page)).toHaveAttribute('aria-expanded', 'false');

    await picker(page).click();

    await expect(picker(page)).toHaveAttribute('aria-expanded', 'true');

    await expect(page.getByRole('listbox')).toBeVisible();

    await expect(page.getByTestId('project-search')).toBeFocused();

    await expect(page.getByTestId('project-option-name')).toHaveText(['All projects', 'demo', 'other']);

    await expect(page.getByTestId('project-option-count')).toHaveText(['Tasks: 5', 'Tasks: 4', 'Tasks: 1']);

    await expect(page.getByRole('option', { name: /demo/ }).getByTestId('project-option-waiting')).toContainText('1');

    await expect(page.getByRole('option', { name: /other/ }).getByTestId('project-option-waiting')).toBeHidden();

    await expect(page.getByRole('option', { selected: true })).toContainText('All projects');
  });

  test('filters the board by the picked project', async ({ page }) => {
    await picker(page).click();

    await page.getByRole('option', { name: /other/ }).click();

    await expect(page.getByRole('listbox')).toBeHidden();

    await expect(picker(page)).toContainText('other');

    await expect(page.locator('.card')).toHaveCount(1);

    await expect(page.getByTestId('needs-human')).toHaveCount(0);

    await expect(page.getByTestId('done-row')).toHaveCount(0);

    await expect(picker(page)).toBeFocused();

    await picker(page).click();

    await page.getByRole('option', { name: /demo/ }).click();

    await expect(page.locator('.card')).toHaveCount(2);

    await picker(page).click();

    await page.getByRole('option', { name: /All projects/ }).click();

    await expect(page.locator('.card')).toHaveCount(3);
  });

  test('narrows the list while typing, ignoring case', async ({ page }) => {
    await picker(page).click();

    await page.getByTestId('project-search').fill('OTH');

    await expect(page.getByTestId('project-option-name')).toHaveText(['other']);

    await page.getByTestId('project-search').fill('zzz');

    await expect(page.getByRole('option')).toHaveCount(0);

    await expect(page.getByTestId('project-empty')).toBeVisible();
  });

  test('works from the keyboard: arrows move, Enter and Space pick, Escape closes back to the button', async ({ page }) => {
    await picker(page).focus();

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('project-search')).toBeFocused();

    await page.keyboard.press('ArrowDown');

    await expect(page.getByRole('option').first()).toBeFocused();

    await page.keyboard.press('ArrowDown');

    await page.keyboard.press('ArrowDown');

    await expect(page.getByRole('option').last()).toBeFocused();

    await page.keyboard.press('ArrowUp');

    await page.keyboard.press('Enter');

    await expect(picker(page)).toContainText('demo');

    await expect(picker(page)).toBeFocused();

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('project-search')).toBeFocused();

    await page.keyboard.press('ArrowDown');

    await page.keyboard.press('ArrowDown');

    await page.keyboard.press('ArrowDown');

    await page.keyboard.press('Space');

    await expect(picker(page)).toContainText('other');

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('project-search')).toBeFocused();

    await page.keyboard.press('Escape');

    await expect(page.getByRole('listbox')).toBeHidden();

    await expect(picker(page)).toBeFocused();
  });

  test('closes when Tab moves the focus out of the picker', async ({ page }) => {
    await picker(page).click();

    await expect(page.getByTestId('project-search')).toBeFocused();

    await page.keyboard.press('Tab');

    await expect(page.getByRole('listbox')).toBeHidden();
  });

  test('closes on a click outside', async ({ page }) => {
    await picker(page).click();

    await expect(page.getByRole('listbox')).toBeVisible();

    await page.getByRole('heading', { level: 1 }).click();

    await expect(page.getByRole('listbox')).toBeHidden();
  });

  test('has touch targets of at least 44px for the picker rows and the Copy button on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    const copy = (await page.getByTestId('row-copy').boundingBox())!;

    expect(copy.height).toBeGreaterThanOrEqual(minimumTouchTarget);

    expect(copy.width).toBeGreaterThanOrEqual(minimumTouchTarget);

    await picker(page).click();

    const heights = await page.getByRole('option').evaluateAll((options) => options.map((option) => option.getBoundingClientRect().height));

    heights.forEach((height) => expect(height).toBeGreaterThanOrEqual(minimumTouchTarget));

    expect((await picker(page).boundingBox())!.height).toBeGreaterThanOrEqual(minimumTouchTarget);
  });
});

test.describe('with a live backend that starts failing', () => {
  test('keeps the old data and shows a banner when the backend starts failing', async ({ page }) => {
    await page.goto(liveUrl);

    await expect(page.getByTestId('status')).toHaveText('Connected');

    await page.route('**/api/board', (route) => route.fulfill({ status: 500, json: { error: 'board unreadable' } }));

    await expect(page.getByTestId('error-banner')).toContainText('board unreadable', { timeout: 15_000 });

    await expect(page.getByTestId('status')).toHaveText('Disconnected');

    await expect(page.locator('.card')).toHaveCount(3);
  });
});

test('shows a banner and no data when the backend is unreachable', async ({ page }) => {
  await page.goto(deadBackendUrl);

  await expect(page.getByTestId('error-banner')).toBeVisible();

  await expect(page.getByTestId('status')).toHaveText('Disconnected');

  await expect(page.locator('.card')).toHaveCount(0);
});
