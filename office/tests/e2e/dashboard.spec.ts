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

  test('shows the history strip of a task: numbered steps, the time each stayed, the reason of a wait, the last one still counting', async ({ page }) => {
    await taskCard(page, 'demo/pick-database').click();

    const steps = page.getByTestId('history-step');

    await expect(steps).toHaveCount(4);

    await expect(steps.nth(0)).toHaveText('1 Intake 30m');

    await expect(steps.nth(1)).toHaveText('2 Needs human 1h00m · intake question');

    await expect(steps.nth(2)).toHaveText('3 Intake 15m');

    await expect(steps.nth(3)).toContainText('4 Needs human');

    await expect(steps.nth(3)).toContainText('· intake question');

    await expect(page.getByTestId('task-manual')).toHaveText('1 manual AC');

    await expect(page.getByTestId('task-visits')).toContainText('2× needed you');

    await expect(page.getByRole('heading', { level: 2, name: 'History' })).toBeVisible();

    await expect(page.getByLabel('Colour legend').getByRole('listitem')).toHaveText(['agent worked', 'waited for you', 'changes asked', 'passed', 'now', 'cancelled']);
  });

  test('shows a dash for a task without history', async ({ page }) => {
    await taskCard(page, 'demo/add-login').click();

    await expect(page.getByTestId('history-empty')).toHaveText('—');

    await expect(page.getByTestId('history-step')).toHaveCount(0);
  });

  test('maps the visits to Review onto the review rounds, and wraps more steps than fit onto further rows at a fixed width', async ({ page }) => {
    await changeBoard(page, (board) => {
      const minutes = [['Intake', 4], ['Needs human', 4], ['Spec', 3], ['Build', 41], ['Review', 3], ['Build', 22], ['Review', 2], ['Approve', 2], ['Build', 5], ['Review', 6]] as const;

      let start = Date.UTC(2026, 10, 20, 8, 0);

      const history = minutes.map(([column, length]) => {
        const entry = { ts: new Date(start).toISOString().replace('.000Z', 'Z'), stage: 'stage', column, reason: column === 'Needs human' ? 'intake-question' : null };

        start += length * 60_000;

        return entry;
      });

      Object.assign(findTask(board, 'ship-report'), { column: 'Review', stage: 'needs-review', history, durations: minutes.map(([column, length]) => ({ column, milliseconds: length * 60_000 })) });
    });

    await page.setViewportSize({ width: 600, height: 900 });

    await taskCard(page, 'demo/ship-report').click();

    const steps = page.getByTestId('history-step');

    await expect(steps).toHaveCount(10);

    await expect(steps.nth(4)).toHaveText('5 Review R1 3m · changes asked');

    await expect(steps.nth(6)).toHaveText('7 Review R2 2m · passed');

    await expect(steps.nth(1)).toContainText('· intake question');

    await expect(steps.nth(9)).toContainText('Review');

    await expect(steps.nth(9)).toContainText('running ·');

    await expect(steps.nth(9)).toHaveAttribute('data-kind', 'now');

    const boxes = await steps.evaluateAll((items) => items.map((item) => item.getBoundingClientRect()));

    boxes.forEach((box) => expect(box.width).toBe(150));

    expect(new Set(boxes.map((box) => Math.round(box.y))).size).toBeGreaterThan(1);

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
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

  test('opens the task page from a card: the hash, the title, the header, the files, and renders one', async ({ page }) => {
    await taskCard(page, 'demo/ship-report').click();

    await expect(page).toHaveURL(/#\/task\/demo\/ship-report$/);

    await expect(page.getByTestId('task-page')).toBeVisible();

    await expect(page.getByTestId('board')).toBeHidden();

    await expect(page.getByRole('dialog')).toHaveCount(0);

    await expect(page.getByTestId('task-title')).toHaveText('Ship report');

    await expect(page.getByTestId('task-title')).toBeFocused();

    await expect(page.getByTestId('task-project')).toHaveText('demo');

    await expect(page.getByTestId('task-column')).toHaveText('Done');

    await expect(page.getByTestId('task-risk')).toContainText('medium risk');

    await expect(page.getByTestId('task-time')).toHaveText('2m');

    await expect(page.getByTestId('task-tokens')).toHaveText('6.0k tokens');

    await expect(page.getByTestId('task-mr')).toHaveAttribute('href', 'https://example.com/demo/merge_requests/1');

    await expect(page.getByTestId('file-group')).toHaveText(['Job', 'Review']);

    await expect(page.locator('.file').first().getByTestId('file-label')).toHaveText('intent.md');

    await expect(page.locator('.file').first()).toHaveAttribute('aria-current', 'true');

    await expect(page.getByTestId('task-body').locator('h1')).toHaveText('Intent: Ship report');
  });

  test('opens the task page from a Needs human row and from the Done rail', async ({ page }) => {
    await page.locator('[data-row="demo/pick-database"]').getByTestId('row-title').click();

    await expect(page).toHaveURL(/#\/task\/demo\/pick-database$/);

    await expect(page.getByTestId('task-page')).toBeVisible();

    await page.getByTestId('task-back').click();

    await expect(page.getByTestId('board')).toBeVisible();

    await expect(page.locator('[data-row="demo/pick-database"]').getByTestId('row-title')).toBeFocused();

    await page.getByTestId('done-title').click();

    await expect(page).toHaveURL(/#\/task\/demo\/ship-report$/);

    await page.goBack();

    await expect(page.getByTestId('done-title')).toBeFocused();
  });

  test('opens the task page from a card with the keyboard', async ({ page }) => {
    await taskCard(page, 'demo/fix-export').focus();

    await page.keyboard.press('Enter');

    await expect(page.getByTestId('task-page')).toBeVisible();
  });

  test('returns to the board with the Back button and with "← Board", restoring the scroll position and the focus', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 500 });

    const card = taskCard(page, 'demo/fix-export');

    await card.scrollIntoViewIfNeeded();

    await page.evaluate(() => window.scrollBy(0, 120));

    const scrolled = await page.evaluate(() => window.scrollY);

    expect(scrolled).toBeGreaterThan(0);

    await card.click();

    await expect(page.getByTestId('task-page')).toBeVisible();

    expect(await page.evaluate(() => window.scrollY)).toBe(0);

    await page.goBack();

    await expect(page.getByTestId('board')).toBeVisible();

    await expect(card).toBeFocused();

    expect(await page.evaluate(() => window.scrollY)).toBe(scrolled);

    await page.goForward();

    await expect(page.getByTestId('task-page')).toBeVisible();

    await page.getByTestId('task-back').click();

    await expect(page.getByTestId('board')).toBeVisible();

    await expect(page).not.toHaveURL(/#/);

    await expect(card).toBeFocused();
  });

  test('opens a task and a file from a link, and leaves for the board from there', async ({ page }) => {
    await page.goto(`${liveUrl}/#/task/demo/ship-report/review%2Fround-1%2Freview-code.md`);

    await expect(page.getByTestId('task-page')).toBeVisible();

    await expect(page.getByTestId('task-verdict')).toHaveText('CHANGES missing a test');

    await expect(page.getByTestId('task-title')).toHaveText('Ship report');

    await expect(page.getByTestId('round-toggle').nth(0)).toHaveAttribute('aria-expanded', 'true');

    await expect(page.getByTestId('round-toggle').nth(1)).toHaveAttribute('aria-expanded', 'true');

    await page.getByTestId('task-back').click();

    await expect(page.getByTestId('board')).toBeVisible();

    await expect(page).not.toHaveURL(/#/);
  });

  test('says so, with a link back, for a task that is not on the board', async ({ page }) => {
    await page.goto(`${liveUrl}/#/task/demo/nope`);

    await expect(page.getByText('This task is not on the board')).toBeVisible();

    await expect(page.getByTestId('task-history')).toBeHidden();

    await page.getByTestId('task-missing-back').click();

    await expect(page.getByTestId('board')).toBeVisible();
  });

  test('puts the selected file in the address, and keeps one history entry for the task', async ({ page }) => {
    await taskCard(page, 'demo/ship-report').click();

    await page.getByTestId('round-toggle').first().click();

    await page.locator('.file', { hasText: 'change.diff' }).first().click();

    await expect(page.getByTestId('task-plain')).toContainText('diff --git');

    await expect(page).toHaveURL(/#\/task\/demo\/ship-report\/review%2Fround-1%2Fchange\.diff$/);

    await page.goBack();

    await expect(page.getByTestId('board')).toBeVisible();
  });

  test('collapses and expands the review rounds, several at once, and keeps them while the board refreshes', async ({ page }) => {
    await taskCard(page, 'demo/ship-report').click();

    const toggles = page.getByTestId('round-toggle');

    await expect(toggles).toHaveCount(2);

    await expect(toggles.nth(0)).toHaveAttribute('aria-expanded', 'false');

    await expect(toggles.nth(1)).toHaveAttribute('aria-expanded', 'true');

    await expect(toggles.nth(0).getByTestId('file-tag')).toHaveText('CHANGES');

    await expect(toggles.nth(1).getByTestId('file-tag')).toHaveText('PASS');

    await expect(page.locator('.file', { hasText: 'review-code.md' })).toHaveCount(1);

    await toggles.nth(0).click();

    await expect(toggles.nth(0)).toHaveAttribute('aria-expanded', 'true');

    await expect(page.locator('.file', { hasText: 'review-code.md' })).toHaveCount(2);

    await page.waitForResponse((response) => response.url().endsWith('/api/board'), { timeout: 15_000 });

    await page.waitForResponse((response) => response.url().includes('/api/tasks/demo/ship-report') && !response.url().includes('/file'), { timeout: 15_000 });

    await expect(toggles.nth(0)).toHaveAttribute('aria-expanded', 'true');

    await expect(toggles.nth(1)).toHaveAttribute('aria-expanded', 'true');

    await toggles.nth(1).click();

    await expect(toggles.nth(1)).toHaveAttribute('aria-expanded', 'false');

    await expect(page.locator('.file', { hasText: 'review-code.md' })).toHaveCount(1);
  });

  test('turns the icon of the running round, and not under reduced motion', async ({ page }) => {
    await changeBoard(page, (board) => {
      Object.assign(findTask(board, 'ship-report'), { column: 'Review', stage: 'needs-review' });
    });

    await page.route('**/api/tasks/demo/ship-report', async (route) => {
      const detail = await (await route.fetch()).json();

      detail.column = 'Review';

      detail.rounds[1].reviews = { code: 'pending', docs: 'pending' };

      await route.fulfill({ json: detail });
    });

    await page.reload();

    await taskCard(page, 'demo/ship-report').click();

    const spinner = page.getByTestId('round-toggle').nth(1).locator('[data-spinning=true]');

    await expect(page.getByTestId('round-toggle').nth(1).getByTestId('file-tag')).toHaveText('running');

    await expect(spinner).toHaveText('progress_activity');

    await expect(spinner).toHaveCSS('animation-name', 'spin');

    await page.emulateMedia({ reducedMotion: 'reduce' });

    await expect(spinner).toHaveCSS('animation-name', 'none');
  });

  test('puts the files in a block above the content on a phone, without sideways scrolling, in light and dark', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });

      await taskCard(page, 'demo/ship-report').click();

      const files = (await page.getByRole('navigation', { name: 'Task files' }).boundingBox())!;

      const content = (await page.getByTestId('task-content').boundingBox())!;

      expect(content.y).toBeGreaterThanOrEqual(files.y + files.height);

      expect(files.width).toBeGreaterThan(300);

      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

      const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);

      expect(background).toBe(colorScheme === 'light' ? 'rgb(243, 244, 247)' : 'rgb(20, 21, 27)');

      await page.getByTestId('task-back').click();
    }
  });

  test('puts the files left of the content on a wide screen', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    await taskCard(page, 'demo/ship-report').click();

    const files = (await page.getByRole('navigation', { name: 'Task files' }).boundingBox())!;

    const content = (await page.getByTestId('task-content').boundingBox())!;

    expect(content.x).toBeGreaterThanOrEqual(files.x + files.width);

    expect(content.y).toBeCloseTo(files.y, -1);
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
