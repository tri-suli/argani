// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PollHandlers, Poller } from '@/types/poller';
import createDashboard from '@/components/dashboard';
import type { TaskFile, TaskRound } from '@/types/task';
import FakeNavigation from '../fake-navigation';
import { FakeTaskClient, sampleDetail, sampleSnapshot, sampleTasks, sampleViews } from '../sample-snapshot';
import sampleMarkdownRenderer from '../sample-markdown-renderer';
import pageMarkup from './page-markup';
import eventually from './eventually';

class FakePoller implements Poller {
  handlers!: PollHandlers;

  start(handlers: PollHandlers) {
    this.handlers = handlers;
  }

  stop() {}
}

// Alpine renders nested x-for templates over several ticks, so assertions on rendered output retry with eventually;
// "nothing happened" assertions first let Alpine and the pending promises flush with Alpine.nextTick().
const markdownRenderer = sampleMarkdownRenderer();

const flush = () => Alpine.nextTick();

const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();

const isShown = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';

const card = () => document.querySelector('[data-task="demo/fix-export"]') as HTMLElement;

const fileButtons = () => [...document.querySelectorAll<HTMLElement>('.file')];

const labelOf = (button: Element) => button.querySelector('[data-testid=file-label]')?.textContent;

const roundToggles = () => [...document.querySelectorAll<HTMLElement>('[data-testid=round-toggle]')];

const press = (key: string, init: KeyboardEventInit = {}, target: EventTarget = document.body) =>
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init }));

const leave = () => (document.querySelector('[data-testid=task-back]') as HTMLElement).click();

const openTask = async () => {
  card().click();

  await eventually(() => {
    expect(text('[data-testid=task-body]')).toContain('Hello');

    expect(fileButtons()).toHaveLength(3);
  });
};

const diffRows = () => [...document.querySelectorAll('[data-testid=diff-row]')].map((row) => row.textContent);

const selectFile = (index: number) => fileButtons()[index].click();

const pollAgain = () => poller.handlers.onSnapshot(sampleSnapshot(), sampleTasks());

let poller: FakePoller;

let taskClient: FakeTaskClient;

let navigation: FakeNavigation;

/** A fresh page; `hash` is what the address says when it loads, `poll` false keeps the first board answer back. */
const mount = async (hash = '', poll = true, configure: (client: FakeTaskClient) => void = () => {}) => {
  poller = new FakePoller();

  taskClient = new FakeTaskClient();

  configure(taskClient);

  navigation = new FakeNavigation(hash);

  document.body.innerHTML = pageMarkup();

  Alpine.initTree(document.body);

  await eventually(() => expect(poller.handlers).toBeDefined());

  if (poll) {
    pollAgain();

    await eventually(() => expect(card()).not.toBeNull());
  }
};

beforeAll(() => {
  Alpine.data('dashboard', () => createDashboard({ poller, taskClient, ...sampleViews(), navigation, markdownRenderer, clipboard: { writeText: async () => {} }, now: () => new Date() }));

  Alpine.start();
});

beforeEach(async () => {
  vi.restoreAllMocks();

  await mount();
});

describe('task page', () => {
  it('shows the board until a task is opened', () => {
    expect(isShown('[data-testid=task-page]')).toBe(false);

    expect(isShown('[data-testid=board]')).toBe(true);

    expect(document.querySelector('[inert]')).toBeNull();

    expect(navigation.hash()).toBe('');
  });

  it('opens on click in place of the board, addressed by the hash, with the title focused and the first file selected', async () => {
    await openTask();

    expect(isShown('[data-testid=task-page]')).toBe(true);

    expect(isShown('[data-testid=board]')).toBe(false);

    expect(navigation.hash()).toBe('#/task/demo/fix-export');

    expect(navigation.entries).toHaveLength(2);

    expect(document.querySelector('[data-testid=task-title]')?.tagName).toBe('H1');

    expect(text('[data-testid=task-title]')).toBe('Fix export');

    await eventually(() => expect(document.activeElement).toBe(document.querySelector('[data-testid=task-title]')));

    expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');

    expect(fileButtons()[1].hasAttribute('aria-current')).toBe(false);
  });

  it('has one main landmark for the task view, not nested in another landmark', async () => {
    await openTask();

    const page = document.querySelector('[data-testid=task-page]') as HTMLElement;

    expect(page.tagName).toBe('MAIN');

    expect(page.querySelector('main')).toBeNull();

    expect(page.closest('section, nav, aside, header, footer')).toBeNull();

    expect(document.querySelector('[data-testid=task-content]')?.tagName).toBe('SECTION');
  });

  it('sets the document title to the task while it is open, and back to the app on the board', async () => {
    expect(document.title).toBe('Argani Office');

    await openTask();

    await eventually(() => expect(document.title).toBe('Fix export · Argani Office'));

    leave();

    await eventually(() => expect(document.title).toBe('Argani Office'));
  });

  it('is no dialog: no scrim, no aria-modal, nothing inert, Escape does nothing', async () => {
    await openTask();

    expect(document.querySelector('[role=dialog], [aria-modal], [data-testid=scrim], [inert]')).toBeNull();

    press('Escape');

    await flush();

    expect(isShown('[data-testid=task-page]')).toBe(true);
  });

  it('lists the job files, then the review under its own heading with the round as a button and its files nested below', async () => {
    await openTask();

    expect([...document.querySelectorAll('[data-testid=file-group]')].map((group) => group.textContent)).toEqual(['Job', 'Review']);

    expect([...document.querySelectorAll('[data-testid=file-label]')].map((label) => label.textContent)).toEqual(['spec.md', 'build.diff', 'Round 1', 'review-code.md']);

    expect(fileButtons().map((button) => button.getAttribute('data-nested'))).toEqual([null, null, 'true']);

    const review = fileButtons()[2];

    expect(review.querySelector('[data-testid=file-tone]')?.getAttribute('data-tone')).toBe('good');

    expect(review.querySelector('[data-testid=file-tone]')?.textContent).toBe('check_circle');

    expect(review.querySelector('[data-testid=file-tag]')?.textContent).toBe('PASS');

    expect(fileButtons()[0].querySelector('[data-testid=file-tone]')?.textContent).toBe('description');
  });

  it('names the tone of a file for screen readers, and nothing for a file without tone', async () => {
    await openTask();

    expect(fileButtons().map((button) => button.querySelector('.sr-only')?.textContent)).toEqual(['', '', ': passed']);
  });

  it('opens with Enter and Space on the card but not from the MR link', async () => {
    press('Enter', {}, card());

    await eventually(() => expect(isShown('[data-testid=task-page]')).toBe(true));

    leave();

    await eventually(() => expect(isShown('[data-testid=task-page]')).toBe(false));

    press(' ', {}, card());

    await eventually(() => expect(isShown('[data-testid=task-page]')).toBe(true));

    leave();

    await eventually(() => expect(isShown('[data-testid=task-page]')).toBe(false));

    const callsBefore = taskClient.taskCalls;

    press('Enter', {}, card().querySelector('a') as HTMLElement);

    await flush();

    expect(taskClient.taskCalls).toBe(callsBefore);

    expect(isShown('[data-testid=task-page]')).toBe(false);
  });

  it('does not open the task when the MR link of the card is clicked', async () => {
    const link = card().querySelector('a') as HTMLElement;

    // keep happy-dom from opening the external URL; the app's own handlers still run
    link.addEventListener('click', (event) => event.preventDefault());

    link.click();

    await flush();

    expect(taskClient.taskCalls).toBe(0);

    expect(isShown('[data-testid=task-page]')).toBe(false);
  });

  it('returns to the board with "← Board", restores the scroll position and gives the focus back to the card', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});

    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(420);

    await openTask();

    scrollTo.mockClear();

    leave();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    expect(isShown('[data-testid=task-page]')).toBe(false);

    await eventually(() => expect(document.activeElement).toBe(card()));

    expect(scrollTo).toHaveBeenCalledWith(0, 420);

    expect(navigation.hash()).toBe('');
  });

  it('returns to the board the same way with the Back button of the browser', async () => {
    await openTask();

    navigation.back();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    await eventually(() => expect(document.activeElement).toBe(card()));
  });

  it('leaves for the board, not for the task the history came from, when the address was edited to another task', async () => {
    await openTask();

    navigation.edit('#/task/demo/older');

    await eventually(() => expect(text('[data-testid=task-title]')).toBe('Older work'));

    leave();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    expect(navigation.hash()).toBe('');
  });

  it('leaves by going back when the task came from the board, also after Back and Forward, so the board is in the history once', async () => {
    await openTask();

    navigation.back();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    navigation.forward();

    await eventually(() => expect(isShown('[data-testid=task-page]')).toBe(true));

    leave();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    expect(navigation.position).toBe(0);

    expect(navigation.entries).toHaveLength(2);
  });

  it('opens a task from a link: the hash names it, and "← Board" leaves without a history entry to go back to', async () => {
    await mount('#/task/demo/fix-export');

    await eventually(() => expect(text('[data-testid=task-body]')).toContain('Hello'));

    expect(isShown('[data-testid=task-page]')).toBe(true);

    expect(isShown('[data-testid=board]')).toBe(false);

    expect(text('[data-testid=task-title]')).toBe('Fix export');

    leave();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    expect(navigation.hash()).toBe('');

    expect(navigation.entries.map((entry) => entry.hash)).toEqual(['']);
  });

  it('shows the slug as the title until the board has arrived, and the task is not "missing" before then', async () => {
    await mount('#/task/demo/fix-export', false);

    await eventually(() => expect(text('[data-testid=task-title]')).toBe('fix-export'));

    expect(isShown('[data-testid=task-missing]')).toBe(false);

    pollAgain();

    await eventually(() => expect(text('[data-testid=task-title]')).toBe('Fix export'));
  });

  it('shows the board for an address that names no task', async () => {
    await mount('#/task/%E0%A4%A/x');

    expect(isShown('[data-testid=board]')).toBe(true);

    expect(isShown('[data-testid=task-page]')).toBe(false);
  });

  it('follows the address: another task, another file of the same task, a file that is not listed, the board', async () => {
    await openTask();

    navigation.edit('#/task/demo/older');

    await eventually(() => expect(text('[data-testid=task-title]')).toBe('Older work'));

    navigation.edit('#/task/demo/fix-export');

    await eventually(() => expect(text('[data-testid=task-title]')).toBe('Fix export'));

    await eventually(() => expect(fileButtons()).toHaveLength(3));

    const callsBefore = taskClient.fileCalls.length;

    navigation.edit('#/task/demo/fix-export');

    navigation.edit('#/task/demo/fix-export/not-listed.md');

    await flush();

    expect(taskClient.fileCalls).toHaveLength(callsBefore);

    navigation.edit('#/task/demo/fix-export/build.diff');

    await eventually(() => expect(fileButtons()[1].getAttribute('aria-current')).toBe('true'));

    navigation.edit('');

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));
  });

  it('replaces the address by the real selection when a link names a file the task does not list', async () => {
    await mount('#/task/demo/fix-export/nope.md');

    await eventually(() => expect(navigation.hash()).toBe('#/task/demo/fix-export/spec.md'));

    expect(navigation.entries).toHaveLength(1);

    expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');

    navigation.edit('#/task/demo/fix-export/also-nope.md');

    await eventually(() => expect(navigation.hash()).toBe('#/task/demo/fix-export/spec.md'));
  });

  it('puts the selected file in the address without adding a history entry, and a link to a file selects it', async () => {
    await openTask();

    selectFile(2);

    await eventually(() => expect(navigation.hash()).toBe('#/task/demo/fix-export/review%2Fround-1%2Freview-code.md'));

    expect(navigation.entries).toHaveLength(2);

    await mount('#/task/demo/fix-export/review%2Fround-1%2Freview-code.md');

    await eventually(() => {
      expect(fileButtons()[2].getAttribute('aria-current')).toBe('true');

      expect(text('[data-testid=task-verdict]')).toBe('PASS ok');
    });
  });

  it('writes the hash of a picked file at once, so a slow file never writes it over the board after Back', async () => {
    await openTask();

    const release: (() => void)[] = [];

    taskClient.fetchFile = (_project, _slug, path) => new Promise((resolve) => release.push(() => resolve(`text of ${path}`)));

    selectFile(1);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/build.diff');

    navigation.back();

    expect(navigation.hash()).toBe('');

    release.forEach((resolve) => resolve());

    await flush();

    expect(navigation.hash()).toBe('');
  });

  it('keeps the hash on the file picked last when the answers arrive out of order', async () => {
    await openTask();

    const release: Record<string, () => void> = {};

    taskClient.fetchFile = (_project, _slug, path) => new Promise((resolve) => (release[path] = () => resolve(`text of ${path}`)));

    selectFile(1);

    selectFile(2);

    release['review/round-1/review-code.md']();

    release['build.diff']();

    await flush();

    expect(navigation.hash()).toBe('#/task/demo/fix-export/review%2Fround-1%2Freview-code.md');

    expect(fileButtons()[2].getAttribute('aria-current')).toBe('true');
  });

  it('switches files; diffs show as rows, other files as plain text, markdown with verdict and summary', async () => {
    await openTask();

    selectFile(1);

    await eventually(() => {
      expect(isShown('[data-testid=task-diff]')).toBe(true);

      expect(isShown('[data-testid=task-plain]')).toBe(false);

      expect(isShown('[data-testid=task-markdown]')).toBe(false);

      expect(diffRows()).toEqual(['+added line', '-removed line']);
    });

    selectFile(2);

    await eventually(() => {
      expect(isShown('[data-testid=task-markdown]')).toBe(true);

      expect(text('[data-testid=task-verdict]')).toBe('PASS ok');

      expect(document.querySelector('[data-testid=task-verdict]')?.getAttribute('data-tone') === 'good').toBe(true);

      expect(isShown('[data-testid=task-summary]')).toBe(true);

      expect(text('[data-testid=task-summary]')).toContain('all good');

      expect(text('[data-testid=task-body]')).toContain('Details');
    });
  });

  it('hides verdict and summary for a plain markdown file', async () => {
    await openTask();

    expect(isShown('[data-testid=task-verdict]')).toBe(false);

    expect(isShown('[data-testid=task-summary]')).toBe(false);
  });

  it('refreshes with the poll while open and keeps the selected file', async () => {
    await openTask();

    selectFile(1);

    await eventually(() => expect(diffRows()).toEqual(['+added line', '-removed line']));

    taskClient.texts['build.diff'] = '+changed\n';

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(diffRows()).toEqual(['+changed']));

    expect(fileButtons()[1].getAttribute('aria-current')).toBe('true');
  });

  it('refetches the file only when the task or the file entry changed', async () => {
    await openTask();

    const fetched = () => taskClient.fileCalls.length;

    const before = fetched();

    pollAgain();

    await eventually(() => expect(taskClient.taskCalls).toBe(2));

    await flush();

    expect(fetched()).toBe(before);

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(fetched()).toBe(before + 1));

    const [spec, diff, review] = sampleDetail().files;

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z', files: [spec, diff, review, { ...review, tone: 'warn' }] });

    pollAgain();

    await eventually(() => expect(taskClient.taskCalls).toBe(4));

    await flush();

    expect(fetched()).toBe(before + 1);

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z', files: [{ ...spec, firstLine: '# Spec v2' }, diff, review] });

    pollAgain();

    await eventually(() => expect(fetched()).toBe(before + 2));
  });

  it('keeps the rendered DOM of an unchanged file across refreshes, and rebuilds it when the text changed', async () => {
    await openTask();

    const emphasis = document.querySelector('[data-testid=task-body] strong') as HTMLElement;

    emphasis.dataset.kept = 'yes';

    const fetched = taskClient.fileCalls.length;

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(taskClient.fileCalls.length).toBe(fetched + 1));

    await flush();

    expect((document.querySelector('[data-testid=task-body] strong') as HTMLElement).dataset.kept).toBe('yes');

    taskClient.texts['spec.md'] = '# Spec\n\nNew **words**';

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T12:00:00Z' });

    pollAgain();

    await eventually(() => expect(text('[data-testid=task-body]')).toContain('New words'));

    expect((document.querySelector('[data-testid=task-body] strong') as HTMLElement).dataset.kept).toBeUndefined();
  });

  it('moves the focus to the title once per open, not with every poll', async () => {
    await openTask();

    await eventually(() => expect(document.activeElement).toBe(document.querySelector('[data-testid=task-title]')));

    fileButtons()[1].focus();

    pollAgain();

    await eventually(() => expect(taskClient.taskCalls).toBe(2));

    await flush();

    expect(document.activeElement).toBe(fileButtons()[1]);
  });

  it('shows nothing, not the previous file, when the newly selected file cannot be loaded', async () => {
    await openTask();

    taskClient.failure = new Error('file too large');

    selectFile(1);

    await eventually(() => expect(text('[data-testid=task-error]')).toBe('file too large'));

    expect(isShown('[data-testid=task-markdown]')).toBe(false);

    expect(document.querySelector('[data-testid=task-plain]')?.textContent).toBe('');

    expect(isShown('[data-testid=task-diff]')).toBe(false);

    taskClient.failure = null;

    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(diffRows()).toEqual(['+added line', '-removed line']));

    expect(text('[data-testid=task-error]')).toBe('');
  });

  it('does not reload while the board is shown', async () => {
    pollAgain();

    await flush();

    expect(taskClient.taskCalls).toBe(0);
  });

  it('falls back to the first file when the selected one disappears', async () => {
    await openTask();

    selectFile(1);

    await eventually(() => expect(fileButtons()[1].getAttribute('aria-current')).toBe('true'));

    taskClient.detail = sampleDetail({ files: [sampleDetail().files[0]] });

    pollAgain();

    await eventually(() => {
      expect(fileButtons().map(labelOf)).toEqual(['spec.md']);

      expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');

      expect(isShown('[data-testid=task-markdown]')).toBe(true);
    });
  });

  it('shows an empty page for a task without files, and no MR link or risk without them', async () => {
    taskClient.detail = sampleDetail({ files: [], mrUrl: null, risk: null });

    card().click();

    await eventually(() => {
      expect(isShown('[data-testid=task-plain]')).toBe(true);

      expect(isShown('[data-testid=task-mr]')).toBe(false);

      expect(isShown('[data-testid=task-risk]')).toBe(false);
    });

    expect(fileButtons()).toHaveLength(0);
  });

  it('shows an error when the task cannot be loaded, and keeps content when a refresh fails', async () => {
    taskClient.failure = new Error('task unreadable');

    card().click();

    await eventually(() => expect(text('[data-testid=task-error]')).toBe('task unreadable'));

    expect(text('[data-testid=task-title]')).toBe('Fix export');

    leave();

    await eventually(() => expect(isShown('[data-testid=task-page]')).toBe(false));

    taskClient.failure = null;

    await openTask();

    expect(text('[data-testid=task-error]')).toBe('');

    taskClient.failure = new Error('later failure');

    const callsBefore = taskClient.taskCalls;

    pollAgain();

    expect(taskClient.taskCalls).toBe(callsBefore + 1);

    await flush();

    expect(text('[data-testid=task-error]')).toBe('');

    expect(text('[data-testid=task-body]')).toContain('Hello');
  });

  it('shows the file error when one file cannot be read', async () => {
    await openTask();

    taskClient.failure = new Error('file too large');

    selectFile(1);

    await eventually(() => expect(text('[data-testid=task-error]')).toBe('file too large'));
  });

  it('drops an answer that arrives after the task page was left', async () => {
    card().click();

    navigation.back();

    await flush();

    expect(isShown('[data-testid=task-page]')).toBe(false);

    expect(document.querySelectorAll('[data-testid=file-label]')).toHaveLength(0);
  });

  it('drops a failure that arrives after the task page was left', async () => {
    taskClient.failure = new Error('late');

    card().click();

    navigation.back();

    await flush();

    expect(text('[data-testid=task-error]')).toBe('');
  });

  it('drops a file answer that arrives after the selection moved on', async () => {
    await openTask();

    selectFile(1);

    selectFile(0);

    await flush();

    expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');

    expect(isShown('[data-testid=task-markdown]')).toBe(true);
  });

  it('drops a file failure that arrives after the task page was left', async () => {
    await openTask();

    taskClient.failure = new Error('late file');

    selectFile(1);

    navigation.back();

    await flush();

    expect(text('[data-testid=task-error]')).toBe('');
  });

  it('says so, with a link back, when the task is not on the board', async () => {
    await mount('#/task/demo/nope');

    await eventually(() => expect(isShown('[data-testid=task-missing]')).toBe(true));

    expect(text('[data-testid=task-missing]')).toContain('This task is not on the board');

    expect(isShown('[data-testid=task-history]')).toBe(false);

    expect(document.querySelector('[data-testid=task-header]')).toBeNull();

    (document.querySelector('[data-testid=task-missing-back]') as HTMLElement).click();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));
  });

  it('says so when the open task vanishes from the board, and leaving it finds no card to focus', async () => {
    await openTask();

    poller.handlers.onSnapshot(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }] }), []);

    await eventually(() => expect(isShown('[data-testid=task-missing]')).toBe(true));

    leave();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    await eventually(() => expect(document.activeElement).toBe(document.querySelector('[data-testid=board-title]')));
  });
});

describe('review rounds in the file list', () => {
  const inRound = (n: number, name: string, firstLine = '', tone: TaskFile['tone'] = null): TaskFile => ({ path: `review/round-${n}/${name}`, group: `Round ${n}`, firstLine, tone });

  const withRounds = (rounds: TaskRound[], overrides = {}) => sampleDetail({
    column: 'Review',
    rounds,
    files: [
      { path: 'intent.md', group: 'Job', firstLine: '# Intent', tone: null },
      inRound(1, 'review-code.md', 'CHANGES missing a test', 'warn'),
      inRound(1, 'change.diff'),
      inRound(2, 'review-code.md', 'PASS ok', 'good'),
      inRound(3, 'review-code.md', 'REVIEWING'),
    ],
    ...overrides,
  });

  const threeRounds: TaskRound[] = [{ n: 1, reviews: { code: 'CHANGES' } }, { n: 2, reviews: { code: 'PASS' } }, { n: 3, reviews: { code: 'pending' } }];

  const textsOf = (detail: ReturnType<typeof withRounds>) => Object.fromEntries(detail.files.map((file) => [file.path, `${file.firstLine}\n`]));

  const expanded = () => roundToggles().map((toggle) => toggle.getAttribute('aria-expanded'));

  const openReview = async (detail = withRounds(threeRounds)) => {
    taskClient.detail = detail;

    taskClient.texts = textsOf(detail);

    card().click();

    await eventually(() => expect(roundToggles()).toHaveLength(3));
  };

  it('shows each round as a button with its outcome, a running round turning, and opens the running round first', async () => {
    await openReview();

    expect(expanded()).toEqual(['false', 'false', 'true']);

    expect(roundToggles().map((toggle) => [toggle.querySelector('[data-testid=file-label]')?.textContent, toggle.querySelector('[data-testid=file-tag]')?.textContent])).toEqual([['Round 1', 'CHANGES'], ['Round 2', 'PASS'], ['Round 3', 'running']]);

    const spinner = roundToggles()[2].querySelectorAll('.icon')[1];

    expect([spinner.textContent, spinner.getAttribute('data-spinning')]).toEqual(['progress_activity', 'true']);

    expect(roundToggles()[0].querySelectorAll('.icon')[1].hasAttribute('data-spinning')).toBe(false);

    expect(roundToggles().map((toggle) => toggle.querySelector('.icon')?.textContent)).toEqual(['chevron_right', 'chevron_right', 'expand_more']);

    expect(fileButtons().map(labelOf)).toEqual(['intent.md', 'review-code.md']);
  });

  it('opens and closes rounds one by one, several at once, and keeps them as they are across refreshes', async () => {
    await openReview();

    roundToggles()[0].click();

    await eventually(() => expect(expanded()).toEqual(['true', 'false', 'true']));

    expect(fileButtons().map(labelOf)).toEqual(['intent.md', 'review-code.md', 'change.diff', 'review-code.md']);

    taskClient.detail = withRounds(threeRounds, { updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(taskClient.taskCalls).toBe(2));

    await flush();

    expect(expanded()).toEqual(['true', 'false', 'true']);

    roundToggles()[2].click();

    await eventually(() => expect(expanded()).toEqual(['true', 'false', 'false']));

    expect(fileButtons().map(labelOf)).toEqual(['intent.md', 'review-code.md', 'change.diff']);
  });

  it('opens the latest round when none is running, and the round of the file a link selects', async () => {
    await openReview(withRounds([{ n: 1, reviews: { code: 'CHANGES' } }, { n: 2, reviews: { code: 'PASS' } }, { n: 3, reviews: { code: 'PASS' } }]));

    expect(expanded()).toEqual(['false', 'false', 'true']);

    await mount('#/task/demo/fix-export/review%2Fround-1%2Fchange.diff', true, (client) => {
      client.detail = withRounds(threeRounds);

      client.texts = textsOf(client.detail);
    });

    await eventually(() => expect(roundToggles()).toHaveLength(3));

    expect(expanded()).toEqual(['true', 'false', 'true']);
  });

  it('marks the selected file of a round with aria-current', async () => {
    await openReview();

    roundToggles()[0].click();

    await eventually(() => expect(fileButtons()).toHaveLength(4));

    fileButtons()[2].click();

    await eventually(() => expect(fileButtons().map((button) => button.getAttribute('aria-current'))).toEqual([null, null, 'true', null]));

    expect(navigation.hash()).toBe('#/task/demo/fix-export/review%2Fround-1%2Fchange.diff');
  });

  it('opens a round that appears while the page is open and is running, once, and leaves the rounds the reader knows as they are', async () => {
    const first = withRounds([{ n: 1, reviews: { code: 'CHANGES' } }], { files: withRounds([]).files.slice(0, 3) });

    taskClient.detail = first;

    taskClient.texts = textsOf(first);

    card().click();

    await eventually(() => expect(roundToggles()).toHaveLength(1));

    expect(expanded()).toEqual(['true']);

    roundToggles()[0].click();

    await eventually(() => expect(expanded()).toEqual(['false']));

    const next = withRounds([{ n: 1, reviews: { code: 'CHANGES' } }, { n: 2, reviews: { code: 'pending' } }], { updatedAt: '2026-11-24T11:00:00Z', files: withRounds([]).files.slice(0, 4) });

    taskClient.detail = next;

    taskClient.texts = textsOf(next);

    pollAgain();

    await eventually(() => expect(expanded()).toEqual(['false', 'true']));

    const decided = withRounds([{ n: 1, reviews: { code: 'CHANGES' } }, { n: 2, reviews: { code: 'PASS' } }, { n: 3, reviews: { code: 'PASS' } }], { updatedAt: '2026-11-24T12:00:00Z' });

    taskClient.detail = decided;

    taskClient.texts = textsOf(decided);

    pollAgain();

    await eventually(() => expect(roundToggles()).toHaveLength(3));

    expect(expanded()).toEqual(['false', 'true', 'false']);
  });

  it('opens the first round when it starts while the page is open', async () => {
    const jobOnly = withRounds([], { files: withRounds([]).files.slice(0, 1) });

    taskClient.detail = jobOnly;

    taskClient.texts = textsOf(jobOnly);

    card().click();

    await eventually(() => expect(fileButtons()).toHaveLength(1));

    expect(roundToggles()).toHaveLength(0);

    const started = withRounds([{ n: 1, reviews: { code: 'pending' } }], { updatedAt: '2026-11-24T11:00:00Z', files: withRounds([]).files.slice(0, 2) });

    taskClient.detail = started;

    taskClient.texts = textsOf(started);

    pollAgain();

    await eventually(() => expect(expanded()).toEqual(['true']));
  });
});
