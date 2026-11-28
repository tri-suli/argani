// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import createDashboard from '@/components/dashboard';
import type { PollHandlers, Poller } from '@/types/poller';
import type { TaskFile } from '@/types/task';
import FakeNavigation from '../fake-navigation';
import FakeReaderEnvironment from '../fake-reader-environment';
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

const SPEC = [
  '# Spec: Install `src/`',
  '',
  'Intent: install-laravel',
  'Status: approved by argani on 2026-11-26',
  'Date: 2026-11-26',
  '',
  '## Summary',
  '',
  'Install the **skeleton**. See [the approach](#approach).',
  '',
  '## Approach',
  '',
  '### Commit order',
  '',
  'Each commit passes.',
  '',
  '```bash',
  'git rebase --exec "npm run check"',
  '```',
  '',
  '```',
  'second block',
  '```',
  '',
  '## Acceptance criteria',
  '',
  '1. [x] The stack starts — verify: `docker compose ps`',
  '2. [ ] The page renders — verify: manual: open it in a browser',
  '3. [ ] no verification here',
  '',
  '## Out of scope',
  '',
  '- Nothing.',
].join('\n');

const files: TaskFile[] = [
  { path: 'spec.md', group: 'Job', firstLine: '# Spec', tone: null },
  { path: 'change.diff', group: 'Job', firstLine: 'diff --git', tone: null },
  { path: 'notes.txt', group: 'Job', firstLine: 'notes', tone: null },
  { path: 'review.md', group: 'Job', firstLine: 'CHANGES missing a test', tone: 'warn' },
];

const DIFF = 'diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n';

const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();

const isShown = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';

const all = (selector: string) => [...document.querySelectorAll<HTMLElement>(selector)];

const fileButtons = () => all('.file');

let poller: FakePoller;

let taskClient: FakeTaskClient;

let environment: FakeReaderEnvironment;

let navigation: FakeNavigation;

let written: string[];

const scrolled: string[] = [];

const mount = async (path = 'spec.md') => {
  poller = new FakePoller();

  taskClient = new FakeTaskClient();

  environment = new FakeReaderEnvironment();

  written = [];

  taskClient.detail = sampleDetail({ files });

  taskClient.texts = { 'spec.md': SPEC, 'change.diff': DIFF, 'notes.txt': 'plain notes', 'review.md': 'CHANGES missing a test\n\n## Summary\n- one\n\n## Details\nmore' };

  navigation = new FakeNavigation(`#/task/demo/fix-export/${encodeURIComponent(path)}`);

  document.body.innerHTML = pageMarkup();

  Alpine.initTree(document.body);

  await eventually(() => expect(poller.handlers).toBeDefined());

  poller.handlers.onSnapshot(sampleSnapshot(), sampleTasks());
};

const pollAgain = () => poller.handlers.onSnapshot(sampleSnapshot(), sampleTasks());

const mountedSpec = async () => {
  await mount();

  await eventually(() => {
    expect(text('[data-testid=reader-title]')).toContain('Spec: Install');

    expect(all('[data-testid=outline-entry]')).toHaveLength(5);

    expect(environment.observers.length).toBeGreaterThan(0);
  });
};

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn(function scrollIntoView(this: Element) {
    scrolled.push(this.id);
  });

  Alpine.data('dashboard', () =>
    createDashboard({ poller, taskClient, ...sampleViews(), readerEnvironment: environment, navigation, markdownRenderer: sampleMarkdownRenderer(), clipboard: { writeText: async (value) => void written.push(value) }, now: () => new Date() }),
  );

  Alpine.start();
});

beforeEach(() => {
  scrolled.length = 0;
});

describe('document reader', () => {
  it('shows the head: file name, status pill, title with inline code, and the meta strip', async () => {
    await mountedSpec();

    expect(text('[data-testid=reader-file]')).toBe('spec.md');

    expect(text('[data-testid=task-verdict]')).toBe('approved by argani');

    expect(document.querySelector('[data-testid=task-status]')?.getAttribute('data-tone')).toBe('good');

    expect(document.querySelector('[data-testid=reader-title]')?.tagName).toBe('H2');

    expect(document.querySelector('[data-testid=reader-title] code')?.textContent).toBe('src/');

    expect(all('[data-testid=meta-entry]').map((entry) => entry.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
      'Intent install-laravel',
      'Status approved by argani on 2026-11-26',
      'Date 2026-11-26',
    ]);

    expect(document.querySelectorAll('[data-testid=task-page] h1')).toHaveLength(1);
  });

  it('shows the summary as a callout with the id of its outline entry, and the body below it', async () => {
    await mountedSpec();

    expect(isShown('[data-testid=task-summary]')).toBe(true);

    expect(document.querySelector('[data-testid=task-summary]')?.id).toBe('doc-summary');

    expect(text('[data-testid=task-summary-body]')).toContain('Install the skeleton.');

    expect(all('[data-testid=task-body] h3').map((heading) => heading.id)).toEqual(['doc-approach', 'doc-acceptance-criteria', 'doc-out-of-scope']);

    expect(document.querySelector('[data-testid=task-body] h4')?.id).toBe('doc-commit-order');
  });

  it('renders acceptance criteria as cards: id, claim, verify chip, manual badge, and a plain item when it does not match', async () => {
    await mountedSpec();

    const cards = all('[data-testid=criterion]');

    expect(cards.map((card) => card.getAttribute('data-manual'))).toEqual([null, 'true']);

    expect(cards.map((card) => card.querySelector('[data-testid=criterion-id]')?.textContent)).toEqual(['AC-1', 'AC-2']);

    expect(cards[0].querySelector('[data-testid=criterion-verify]')?.textContent).toContain('docker compose ps');

    expect(cards[0].querySelector('[data-testid=criterion-manual]')).toBeNull();

    expect(cards[1].querySelector('[data-testid=criterion-verify]')).toBeNull();

    expect(cards[1].querySelector('[data-testid=criterion-manual]')?.textContent).toContain('manual');

    expect(cards[1].querySelector('[data-testid=criterion-manual]')?.textContent).toContain('open it in a browser');

    expect(cards.map((card) => card.querySelector('[data-testid=criterion-state]')?.textContent?.trim())).toEqual(['Checked', 'Not checked']);

    expect(cards.map((card) => card.querySelector('[data-testid=criterion-box]')?.textContent)).toEqual(['check_box', 'check_box_outline_blank']);

    expect(text('[data-testid=task-body]')).toContain('no verification here');
  });

  it('lists the sections in the outline with the count of criteria, and the words and minutes', async () => {
    await mountedSpec();

    expect(all('[data-testid=outline-entry]').map((entry) => entry.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
      'Summary',
      'Approach',
      'Commit order',
      'Acceptance criteria2',
      'Out of scope',
    ]);
  });

  it('puts a code block in its own box with the language, the exact text and a Copy button that says Copied on the latest click', async () => {
    await mountedSpec();

    const blocks = all('[data-testid=code-block]');

    expect(blocks.map((block) => block.querySelector('[data-testid=code-language]')?.textContent)).toEqual(['bash', '']);

    expect(blocks[0].querySelector('pre code')?.textContent).toBe('git rebase --exec "npm run check"');

    const [first, second] = all('[data-testid=code-copy]');

    expect(first.textContent).toBe('Copy');

    first.click();

    await eventually(() => expect(first.textContent).toBe('Copied'));

    expect(written).toEqual(['git rebase --exec "npm run check"']);

    expect(first.getAttribute('aria-label')).toBe('Copy code');

    second.click();

    await eventually(() => expect(second.textContent).toBe('Copied'));

    expect(first.textContent).toBe('Copy');

    expect(written[1]).toBe('second block');
  });

  it('does not move the Copied feedback to another block when a poll changes the document', async () => {
    await mountedSpec();

    const [first] = all('[data-testid=code-copy]');

    first.click();

    await eventually(() => expect(first.textContent).toBe('Copied'));

    taskClient.texts['spec.md'] = SPEC.replace('## Approach', '## Approach\n\n```sh\necho inserted\n```');

    taskClient.detail = sampleDetail({ files, updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(all('[data-testid=code-copy]')).toHaveLength(3));

    expect(all('[data-testid=code-copy]').map((button) => button.textContent)).toEqual(['Copy', 'Copy', 'Copy']);
  });

  it('scrolls to a section from the outline, highlights it and leaves the route alone', async () => {
    await mountedSpec();

    const hash = navigation.hash();

    const entry = all('[data-testid=outline-entry]')[3];

    expect(entry.tagName).toBe('BUTTON');

    expect(entry.getAttribute('href')).toBeNull();

    entry.click();

    await eventually(() => expect(entry.getAttribute('aria-current')).toBe('location'));

    expect(scrolled).toEqual(['doc-acceptance-criteria']);

    expect(navigation.hash()).toBe(hash);

    expect(all('[data-testid=outline-entry]').filter((other) => other.hasAttribute('aria-current'))).toHaveLength(1);
  });

  it('highlights the section the reader scrolls to', async () => {
    await mountedSpec();

    await eventually(() => expect(all('[data-testid=outline-entry]')[0].getAttribute('aria-current')).toBe('location'));

    environment.move({ 'doc-out-of-scope': 'zone' });

    await eventually(() => expect(all('[data-testid=outline-entry]')[4].getAttribute('aria-current')).toBe('location'));

    expect(all('[data-testid=outline-entry]')[0].hasAttribute('aria-current')).toBe(false);
  });

  it('follows an in-document link of the markdown without changing the route', async () => {
    await mountedSpec();

    const hash = navigation.hash();

    const link = document.querySelector('[data-testid=task-summary-body] a') as HTMLAnchorElement;

    expect(link.getAttribute('href')).toBe('#approach');

    expect(link.hasAttribute('target')).toBe(false);

    const click = new MouseEvent('click', { bubbles: true, cancelable: true });

    link.dispatchEvent(click);

    expect(click.defaultPrevented).toBe(true);

    expect(scrolled).toContain('doc-approach');

    expect(navigation.hash()).toBe(hash);
  });

  it('keeps the document, the observer and the highlight across a poll that changes nothing', async () => {
    await mountedSpec();

    const observers = environment.observers.length;

    const title = document.querySelector('[data-testid=reader-title]') as HTMLElement;

    environment.move({ 'doc-out-of-scope': 'zone' });

    await eventually(() => expect(all('[data-testid=outline-entry]')[4].getAttribute('aria-current')).toBe('location'));

    taskClient.detail = sampleDetail({ files, updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(taskClient.fileCalls.length).toBeGreaterThan(1));

    await Alpine.nextTick();

    expect(environment.observers).toHaveLength(observers);

    expect(document.querySelector('[data-testid=reader-title]')).toBe(title);

    expect(all('[data-testid=outline-entry]')[4].getAttribute('aria-current')).toBe('location');
  });

  it('tracks the new sections when the file changes, and stops observing when the task page is left', async () => {
    await mountedSpec();

    const observers = environment.observers.length;

    taskClient.texts['spec.md'] = `${SPEC}\n\n## Risks\n\nText.`;

    taskClient.detail = sampleDetail({ files, updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => {
      expect(all('[data-testid=outline-entry]')).toHaveLength(6);

      expect(environment.observers.length).toBeGreaterThan(observers);
    });

    (document.querySelector('[data-testid=task-back]') as HTMLElement).click();

    await eventually(() => expect(environment.latest.disconnected).toBe(true));
  });

  it('reads a review file with the same reader: the verdict is the status pill and the summary a callout', async () => {
    await mount('review.md');

    await eventually(() => {
      expect(text('[data-testid=task-verdict]')).toBe('CHANGES missing a test');

      expect(document.querySelector('[data-testid=task-status]')?.getAttribute('data-tone')).toBe('warn');

      expect(isShown('[data-testid=task-summary]')).toBe(true);

      expect(isShown('[data-testid=reader-title]')).toBe(false);

      expect(isShown('[data-testid=task-meta]')).toBe(false);
    });
  });
});

describe('diff reader', () => {
  it('shows a diff as rows told apart by kind, with the file name and the line count, and no note when nothing is cut', async () => {
    await mount('change.diff');

    await eventually(() => expect(all('[data-testid=diff-row]')).toHaveLength(6));

    expect(all('[data-testid=diff-row]').map((row) => row.getAttribute('data-kind'))).toEqual(['file', 'file', 'file', 'hunk', 'remove', 'add']);

    expect(all('[data-testid=diff-row]')[0].getAttribute('data-start')).toBe('true');

    expect(all('[data-testid=diff-row]')[1].hasAttribute('data-start')).toBe(false);

    expect(isShown('[data-testid=diff-note]')).toBe(false);

    expect(isShown('[data-testid=task-markdown]')).toBe(false);

    expect(text('[data-testid=task-diff] p')).toBe('change.diff6 lines');
  });

  it('keeps the text of the file out of the hidden plain-text view while the diff or the document is shown', async () => {
    await mount('change.diff');

    await eventually(() => expect(all('[data-testid=diff-row]')).toHaveLength(6));

    expect(document.querySelector('[data-testid=task-plain]')?.textContent).toBe('');

    await mount('spec.md');

    await eventually(() => expect(text('[data-testid=reader-title]')).toContain('Spec: Install'));

    expect(document.querySelector('[data-testid=task-plain]')?.textContent).toBe('');
  });

  it('caps a huge diff and says how many lines there are', async () => {
    await mount('change.diff');

    taskClient.texts['change.diff'] = Array.from({ length: 2000 }, (_, index) => `+line ${index}`).join('\n');

    taskClient.detail = sampleDetail({ files, updatedAt: '2026-11-24T11:00:00Z' });

    pollAgain();

    await eventually(() => expect(text('[data-testid=diff-note]')).toBe('Showing the first 1,500 lines of 2,000.'));

    expect(all('[data-testid=diff-row]')).toHaveLength(1500);
  });

  it('keeps other files as plain text', async () => {
    await mount('notes.txt');

    await eventually(() => expect(text('[data-testid=task-plain]')).toBe('plain notes'));

    expect(isShown('[data-testid=task-diff]')).toBe(false);

    expect(isShown('[data-testid=task-markdown]')).toBe(false);

    expect(fileButtons()).toHaveLength(4);
  });
});
