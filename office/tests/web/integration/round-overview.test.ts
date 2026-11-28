// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import type { PollHandlers, Poller } from '@/types/poller';
import createDashboard from '@/components/dashboard';
import type { TaskDetail, TaskFile } from '@/types/task';
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

/** Holds back the answer for chosen files until `release` is called, to make a slow answer arrive late. */
class GatedTaskClient extends FakeTaskClient {
  gated = new Set<string>();

  private waiting: (() => void)[] = [];

  async fetchFile(project: string, slug: string, path: string) {
    const text = await super.fetchFile(project, slug, path);

    if (this.gated.has(path)) {
      await new Promise<void>((resolve) => this.waiting.push(resolve));
    }

    return text;
  }

  release() {
    this.gated.clear();

    this.waiting.splice(0).forEach((resolve) => resolve());
  }

  /** Holds back the answer for the task itself until `openDetail` is called. */
  private detailGate: Promise<void> | null = null;

  private openGate: () => void = () => {};

  holdDetail() {
    this.detailGate = new Promise<void>((resolve) => {
      this.openGate = resolve;
    });
  }

  openDetail() {
    this.openGate();
  }

  async fetchTask() {
    await this.detailGate;

    return super.fetchTask();
  }
}

const markdownRenderer = sampleMarkdownRenderer();

const flush = () => Alpine.nextTick();

const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();

const all = (selector: string) => [...document.querySelectorAll<HTMLElement>(selector)];

const isShown = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';

const press = (key: string, target: EventTarget = document.body) => target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));

const reviewFile = (round: number, name: string, firstLine: string): TaskFile => ({ path: `review/round-${round}/review-${name}.md`, group: `Round ${round}`, firstLine, tone: null });

const CLOSING = '=== END OF REVIEW ===';

const CODE_ROUND_1 = ['CHANGES the per-commit check corrupts the config', '- [Important] a.sh:6 - What: `git init` runs on the **real** repository. Why: it breaks the checkout. Fix: unset `GIT_DIR`.', '- [Nit] b.md:2 - What: typo. Why: reads careless. Fix: fix it.', '- [Important] c.sh:9 - What: second. Why: y. Fix: f.', CLOSING, ''].join('\n');

const SECURITY_ROUND_1 = ['PASS no secret leaks', '- [Nit] compose.yaml:12 - What: port bound on all interfaces. Why: exposure. Fix: bind to 127.0.0.1.', CLOSING, ''].join('\n');

const detailWithRounds = (overrides: Partial<TaskDetail> = {}): TaskDetail => sampleDetail({
  column: 'Review',
  updatedAt: '2026-11-24T09:00:00Z',
  rounds: [{ n: 1, reviews: { code: 'CHANGES', security: 'PASS' } }, { n: 2, reviews: { code: 'pending', security: 'pending' } }],
  reviewers: ['code', 'security'],
  models: { reviewers: { code: 'opus', security: 'inherit' } },
  files: [
    { path: 'spec.md', group: 'Job', firstLine: '# Spec', tone: null },
    reviewFile(1, 'code', 'CHANGES the per-commit check corrupts the config'),
    reviewFile(1, 'security', 'PASS no secret leaks'),
    { path: 'review/round-1/change.diff', group: 'Round 1', firstLine: 'diff --git', tone: null },
    reviewFile(2, 'code', 'PASS half'),
    reviewFile(2, 'security', 'PASS half'),
  ],
  ...overrides,
});

let poller: FakePoller;

let taskClient: GatedTaskClient;

let navigation: FakeNavigation;

const mount = async (hash = '', configure: (client: GatedTaskClient) => void = () => {}) => {
  poller = new FakePoller();

  taskClient = new GatedTaskClient();

  taskClient.detail = detailWithRounds();

  taskClient.texts = {
    'spec.md': '# Spec\n\nHello',
    'review/round-1/review-code.md': CODE_ROUND_1,
    'review/round-1/review-security.md': SECURITY_ROUND_1,
    'review/round-2/review-code.md': 'PASS half\n- [Nit] z:1 - What: not final.',
    'review/round-2/review-security.md': 'PASS half',
  };

  configure(taskClient);

  navigation = new FakeNavigation(hash);

  document.body.innerHTML = pageMarkup();

  Alpine.initTree(document.body);

  await eventually(() => expect(poller.handlers).toBeDefined());

  poller.handlers.onSnapshot(sampleSnapshot(), sampleTasks());
};

const pollAgain = () => poller.handlers.onSnapshot(sampleSnapshot(), sampleTasks());

const overviewRow = (round: number) => all('[data-testid=round-overview-row]').find((row) => row.dataset.round === String(round)) as HTMLElement;

const roundToggle = (round: number) => all('[data-testid=round-toggle]').find((row) => row.dataset.round === String(round)) as HTMLElement;

const cards = () => all('[data-testid=reviewer-card]');

const findings = () => all('[data-testid=finding]');

const chips = () => all('[data-testid=filter-chip]');

const button = () => document.querySelector('[data-testid=round-picker]') as HTMLElement;

const menuOptions = () => all('[data-testid=round-option]');

const openOverview = async (round: number) => {
  if (!overviewRow(round)) {
    roundToggle(round).click();
  }

  await eventually(() => expect(overviewRow(round)).toBeDefined());

  overviewRow(round).click();

  await eventually(() => expect(text('[data-testid=round-title]')).toBe(`Round ${round}`));
};

beforeAll(() => {
  Alpine.data('dashboard', () => createDashboard({ poller, taskClient, ...sampleViews(), navigation, markdownRenderer, clipboard: { writeText: async () => {} }, now: () => new Date() }));

  Alpine.start();
});

beforeEach(async () => {
  await mount('#/task/demo/fix-export');

  await eventually(() => expect(text('[data-testid=task-body]')).toContain('Hello'));
});

describe('round overview: the entry in the file list', () => {
  it('keeps the first file selected on open and offers Overview as the first entry of an open round only', async () => {
    expect(all('.file')[0].getAttribute('aria-current')).toBe('true');

    expect(isShown('[data-testid=round-overview]')).toBe(false);

    await eventually(() => expect(all('[data-testid=round-overview-row]').map((row) => row.dataset.round)).toEqual(['2']));

    expect(all('[data-testid=file-label]').map((label) => label.textContent)).toEqual(['spec.md', 'Round 1', 'Round 2', 'review-code.md', 'review-security.md']);

    roundToggle(1).click();

    await eventually(() => expect(all('[data-testid=round-overview-row]').map((row) => row.dataset.round)).toEqual(['1', '2']));

    const labels = all('[data-testid=file-label], [data-testid=overview-label]').map((label) => label.textContent);

    expect(labels.slice(0, 5)).toEqual(['spec.md', 'Round 1', 'Overview', 'review-code.md', 'review-security.md']);

    roundToggle(1).click();

    await eventually(() => expect(all('[data-testid=round-overview-row]').map((row) => row.dataset.round)).toEqual(['2']));
  });

  it('opens the overview on click: the address names it, the reader gives way, and the row is the current one', async () => {
    await openOverview(1);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/round/1');

    expect(navigation.entries).toHaveLength(1);

    expect(isShown('[data-testid=round-overview]')).toBe(true);

    expect(isShown('[data-testid=task-markdown]')).toBe(false);

    expect(isShown('[data-testid=task-plain]')).toBe(false);

    expect(overviewRow(1).getAttribute('aria-current')).toBe('true');

    expect(all('.file').some((row) => row.hasAttribute('aria-current'))).toBe(false);
  });

  it('opens straight from a link, also in a round the list shows closed', async () => {
    await mount('#/task/demo/fix-export/round/1');

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 1'));

    await eventually(() => expect(overviewRow(1).getAttribute('aria-current')).toBe('true'));

    await eventually(() => expect(cards()).toHaveLength(2));
  });

  it('shows the plain first file with the address corrected when the link names a round that does not exist', async () => {
    await mount('#/task/demo/fix-export/round/9');

    await eventually(() => expect(text('[data-testid=task-body]')).toContain('Hello'));

    expect(isShown('[data-testid=round-overview]')).toBe(false);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/spec.md');
  });

  it('follows the address with Back and Forward between the overview and a file', async () => {
    await openOverview(1);

    navigation.edit('#/task/demo/fix-export/spec.md');

    await eventually(() => expect(isShown('[data-testid=round-overview]')).toBe(false));

    await eventually(() => expect(text('[data-testid=task-body]')).toContain('Hello'));

    navigation.edit('#/task/demo/fix-export/round/2');

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 2'));

    expect(isShown('[data-testid=round-overview]')).toBe(true);
  });

  it('opens a file of the round from the list after the overview and drops the overview', async () => {
    await openOverview(1);

    all('.file').find((row) => row.textContent?.includes('review-code.md'))?.click();

    await eventually(() => expect(isShown('[data-testid=round-overview]')).toBe(false));

    await eventually(() => expect(text('[data-testid=reader-file]')).toBe('review-code.md'));

    expect(overviewRow(1).hasAttribute('aria-current')).toBe(false);
  });
});

describe('round overview: leaving the overview and invalid round numbers', () => {
  it('does not come back with the Round menu open, whether the overview was left for a file or the task page was left', async () => {
    await openOverview(1);

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    navigation.edit('#/task/demo/fix-export/spec.md');

    await eventually(() => expect(isShown('[data-testid=round-overview]')).toBe(false));

    navigation.edit('#/task/demo/fix-export/round/1');

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 1'));

    expect(isShown('[data-testid=round-menu]')).toBe(false);

    expect(button().getAttribute('aria-expanded')).toBe('false');

    expect(menuOptions().some((option) => option === document.activeElement)).toBe(false);

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    (document.querySelector('[data-testid=task-back]') as HTMLElement).click();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    navigation.edit('#/task/demo/fix-export/round/1');

    await eventually(() => {
      expect(cards()).toHaveLength(2);

      expect(isShown('[data-testid=round-menu]')).toBe(false);
    });
  });

  it.each(['0', '-3', 'x'])('opens the task with the address corrected for the round number %s, not the board', async (number) => {
    await mount(`#/task/demo/fix-export/round/${number}`);

    await eventually(() => expect(text('[data-testid=task-body]')).toContain('Hello'));

    expect(isShown('[data-testid=task-page]')).toBe(true);

    expect(isShown('[data-testid=round-overview]')).toBe(false);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/spec.md');
  });

  it('puts the round that is shown back in the address when it is edited to an invalid number', async () => {
    await openOverview(1);

    navigation.edit('#/task/demo/fix-export/round/0');

    await eventually(() => expect(navigation.hash()).toBe('#/task/demo/fix-export/round/1'));

    expect(text('[data-testid=round-title]')).toBe('Round 1');
  });
});

describe('round overview: addresses that name a round', () => {
  it('stays where it is for the round already shown, and puts the shown round back for a round that does not exist', async () => {
    await openOverview(1);

    await eventually(() => expect(cards()).toHaveLength(2));

    const calls = taskClient.fileCalls.length;

    navigation.edit('#/task/demo/fix-export/round/1');

    await flush();

    expect(taskClient.fileCalls.length).toBe(calls);

    navigation.edit('#/task/demo/fix-export/round/9');

    await eventually(() => expect(navigation.hash()).toBe('#/task/demo/fix-export/round/1'));

    expect(text('[data-testid=round-title]')).toBe('Round 1');
  });

  it('applies a round named while the task is still loading once the task has arrived, and keeps the address', async () => {
    taskClient.holdDetail();

    await mount('#/task/demo/fix-export');

    navigation.edit('#/task/demo/fix-export/round/1');

    await flush();

    taskClient.openDetail();

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 1'));

    await eventually(() => expect(cards()).toHaveLength(2));

    expect(isShown('[data-testid=round-overview]')).toBe(true);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/round/1');
  });

  it('applies a file named while the task is still loading the same way', async () => {
    taskClient.holdDetail();

    await mount('#/task/demo/fix-export/round/1');

    navigation.edit('#/task/demo/fix-export/spec.md');

    await flush();

    taskClient.openDetail();

    await eventually(() => expect(text('[data-testid=reader-file]')).toBe('spec.md'));

    expect(isShown('[data-testid=round-overview]')).toBe(false);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/spec.md');
  });

  it('leaves the selection alone when the address names only the task while it is loading', async () => {
    taskClient.holdDetail();

    await mount('#/task/demo/fix-export/round/1');

    navigation.edit('#/task/demo/fix-export');

    await flush();

    taskClient.openDetail();

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 1'));
  });

  it('lists a round the dropdown opens, though the list had it closed', async () => {
    await openOverview(2);

    expect(roundToggle(1).getAttribute('aria-expanded')).toBe('false');

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    menuOptions()[0].click();

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 1'));

    expect(roundToggle(1).getAttribute('aria-expanded')).toBe('true');

    expect(overviewRow(1).getAttribute('aria-current')).toBe('true');
  });
});

describe('round overview: the round and its reviewers', () => {
  it('shows the title, the verdict, the sentence of the data and one card per reviewer file', async () => {
    await openOverview(1);

    await eventually(() => expect(cards()).toHaveLength(2));

    expect(document.querySelector('[data-testid=round-title]')?.tagName).toBe('H2');

    expect(text('[data-testid=round-status]')).toBe('errorCHANGES');

    expect(text('[data-testid=round-summary]')).toBe('1 of 2 reviewers asked for changes · 2 important findings, 2 nits');

    const code = cards()[0];

    expect(code.dataset.reviewer).toBe('code');

    expect(code.dataset.tone).toBe('warn');

    expect(code.querySelector('h3')?.textContent).toBe('code');

    expect(code.querySelector('[data-testid=reviewer-verdict]')?.textContent?.trim()).toBe('errorCHANGES');

    expect(code.querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('the per-commit check corrupts the config');

    expect(code.querySelector('[data-testid=reviewer-counts]')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('2 important · 1 nit · opus');

    expect(cards()[1].dataset.tone).toBe('good');

    expect(cards()[1].querySelector('[data-testid=reviewer-counts]')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('0 important · 1 nit');
  });

  it('links a card to the reviewer file with a push, so Back returns to the overview', async () => {
    await openOverview(1);

    await eventually(() => expect(cards()).toHaveLength(2));

    const link = cards()[0].querySelector('[data-testid=reviewer-link]') as HTMLAnchorElement;

    expect(link.getAttribute('href')).toBe('#/task/demo/fix-export/review%2Fround-1%2Freview-code.md');

    link.click();

    await eventually(() => expect(text('[data-testid=reader-file]')).toBe('review-code.md'));

    expect(isShown('[data-testid=round-overview]')).toBe(false);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/review%2Fround-1%2Freview-code.md');

    navigation.back();

    await eventually(() => expect(isShown('[data-testid=round-overview]')).toBe(true));

    await eventually(() => expect(cards()).toHaveLength(2));

    expect(navigation.hash()).toBe('#/task/demo/fix-export/round/1');
  });

  it('shows a running round with the spinner and reviewers that have not reported, without findings of a half-written file', async () => {
    await openOverview(2);

    await eventually(() => expect(cards()).toHaveLength(2));

    expect(text('[data-testid=round-status]')).toBe('progress_activityRUNNING');

    expect(document.querySelector('[data-testid=round-status] .icon')?.getAttribute('data-spinning')).toBe('true');

    expect(text('[data-testid=round-summary]')).toBe('The reviewers have not reported yet');

    expect(cards().map((card) => card.querySelector('[data-testid=reviewer-verdict]')?.textContent?.trim())).toEqual(['progress_activityRUNNING', 'progress_activityRUNNING']);

    expect(cards()[0].querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('Has not reported yet.');

    expect(findings()).toHaveLength(0);

    expect(text('[data-testid=findings-empty]')).toBe('No findings yet. This page fills in as each reviewer finishes.');
  });

  it('marks the request of the human as coming from the human', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.detail = detailWithRounds({
        rounds: [{ n: 1, reviews: { code: 'PASS', human: 'CHANGES' } }],
        files: [reviewFile(1, 'code', 'PASS ok'), reviewFile(1, 'human', 'CHANGES owner decision')],
      });

      client.texts['review/round-1/review-code.md'] = `PASS ok\n${CLOSING}\n`;

      client.texts['review/round-1/review-human.md'] = `CHANGES owner decision\n\n- [Important] Remove the sets.\n  - first\n  - second\n\n${CLOSING}\n`;
    });

    await eventually(() => expect(cards()).toHaveLength(2));

    const human = cards()[1];

    expect(human.dataset.reviewer).toBe('human');

    expect(human.querySelector('[data-testid=reviewer-origin]')?.textContent).toContain('from the human');

    expect((cards()[0].querySelector('[data-testid=reviewer-origin]') as HTMLElement).style.display).toBe('none');

    expect(findings()).toHaveLength(1);

    expect(findings()[0].querySelector('[data-testid=finding-reviewer]')?.textContent?.trim()).toBe('human');

    expect(findings()[0].querySelectorAll('li')).toHaveLength(2);
  });

  it('says a file holds more than findings, and that a file could not be read', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.texts['review/round-1/review-security.md'] = `PASS ok\nNotes: checked the spec.\n${CLOSING}\n`;
    });

    await eventually(() => expect(cards()[1].querySelector('[data-testid=reviewer-other]')?.textContent).toBe('Also holds text that is not a finding: shown below the findings.'));

    await mount('#/task/demo/fix-export/round/1', (client) => {
      const fetchFile = client.fetchFile.bind(client);

      client.fetchFile = async (project, slug, path) => {
        if (path.endsWith('review-security.md')) throw new Error('boom');

        return fetchFile(project, slug, path);
      };
    });

    await eventually(() => expect(cards()[1].querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('This file could not be read.'));

    expect(text('[data-testid=task-error]')).toBe('boom');
  });
});

describe('round overview: findings and filter', () => {
  it('lists the findings of all reviewers, Important first, as cards with severity, location, reviewer and What, Why, Fix', async () => {
    await openOverview(1);

    await eventually(() => expect(findings()).toHaveLength(4));

    expect(findings().map((finding) => finding.dataset.severity)).toEqual(['important', 'important', 'nit', 'nit']);

    const first = findings()[0];

    expect(first.querySelector('[data-testid=finding-severity]')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('priority_highImportant');

    expect(first.querySelector('[data-testid=finding-location]')?.textContent).toBe('a.sh:6');

    expect(first.querySelector('[data-testid=finding-reviewer]')?.textContent?.trim()).toBe('code');

    expect([...first.querySelectorAll('dt')].filter((dt) => dt.style.display !== 'none').map((dt) => dt.textContent)).toEqual(['What', 'Why', 'Fix']);

    expect(first.querySelector('dd code')?.textContent).toBe('git init');

    expect(first.querySelector('dd strong')?.textContent).toBe('real');

    expect(first.querySelector('[data-kind=fix] dd, dd[data-kind=fix]')?.textContent).toBe('unset GIT_DIR.');
  });

  it('shows chips with the counts, filters by severity, and keeps the choice over a poll', async () => {
    await openOverview(1);

    await eventually(() => expect(chips().map((chip) => chip.textContent?.replace(/\s+/g, ' ').trim())).toEqual(['All 4', 'Important 2', 'Nits 2']));

    expect(chips().map((chip) => chip.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false']);

    chips()[1].click();

    await eventually(() => expect(findings()).toHaveLength(2));

    expect(chips().map((chip) => chip.getAttribute('aria-pressed'))).toEqual(['false', 'true', 'false']);

    expect(text('[data-testid=findings-count]')).toBe('Showing 2 of 4 findings');

    const kept = findings()[0];

    pollAgain();

    await flush();

    expect(findings()).toHaveLength(2);

    expect(findings()[0]).toBe(kept);

    chips()[2].click();

    await eventually(() => expect(findings().map((finding) => finding.dataset.severity)).toEqual(['nit', 'nit']));
  });

  it('resets the filter when the round changes', async () => {
    await openOverview(1);

    await eventually(() => expect(findings()).toHaveLength(4));

    chips()[1].click();

    await eventually(() => expect(findings()).toHaveLength(2));

    await openOverview(2);

    expect(chips().map((chip) => chip.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false']);

    await openOverview(1);

    await eventually(() => expect(findings()).toHaveLength(4));
  });

  it('says so when a filter leaves nothing, and when a passing round has no findings', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.detail = detailWithRounds({ column: 'Done', rounds: [{ n: 1, reviews: { code: 'PASS' } }], files: [reviewFile(1, 'code', 'PASS ok')] });

      client.texts['review/round-1/review-code.md'] = `PASS ok\n${CLOSING}\n`;
    });

    await eventually(() => expect(text('[data-testid=round-status]')).toBe('check_circlePASS'));

    await eventually(() => expect(text('[data-testid=round-summary]')).toBe('The reviewer passed · no findings'));

    expect(text('[data-testid=findings-empty]')).toBe('No finding cards in this round.');

    chips()[1].click();

    await eventually(() => expect(text('[data-testid=findings-empty]')).toBe('No important finding in this round.'));

    expect(isShown('[data-testid=findings-empty]')).toBe(true);
  });

  it('draws hostile text as text: no script, no handler, no javascript link in the page', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.texts['review/round-1/review-code.md'] = [
        'CHANGES <img src=x onerror=alert(1)>',
        '- [Important] <script>alert(1)</script>.ts:1 - What: <script>alert(2)</script><img src=x onerror=alert(3)> [x](javascript:alert(4)). Why: <b onclick=alert(5)>y</b>. Fix: ok.',
        CLOSING,
        '',
      ].join('\n');
    });

    await eventually(() => expect(findings().length).toBeGreaterThan(0));

    const overview = document.querySelector('[data-testid=round-overview]') as HTMLElement;

    expect(overview.querySelector('script, img, [onerror], [onclick]')).toBeNull();

    expect(overview.innerHTML).not.toContain('javascript:');

    expect(text('[data-testid=finding-location]')).toBe('<script>alert(1)</script>.ts:1');
  });
});

describe('round overview: markup in the text of a finding', () => {
  it('adds no heading and no id of its own: one h1 stays, ids stay unique', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.texts['review/round-1/review-code.md'] = [
        'CHANGES x',
        '- [Important] a.ts:1 - What: <h1 id="round-listbox">big</h1> text. Why: <a id="round-picker" name="top">y</a>. Fix: ok.',
        CLOSING,
        '',
      ].join('\n');
    });

    await eventually(() => expect(findings().length).toBeGreaterThan(0));

    expect(all('[data-testid=task-page] h1')).toHaveLength(1);

    expect(document.querySelectorAll('#round-listbox')).toHaveLength(1);

    expect(document.querySelector('[data-testid=finding] [id], [data-testid=finding] [name]')).toBeNull();

    expect(text('[data-testid=finding] dd')).toContain('big');
  });
});

describe('round overview: links in the text of a finding', () => {
  it('leaves the address alone when a link inside the text points at a fragment', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.texts['review/round-1/review-code.md'] = ['CHANGES x', '- [Important] a.ts:1 - What: see [the section](#notes) and [docs](https://example.test). Why: y. Fix: ok.', '', 'See [below](#more).', CLOSING, ''].join('\n');
    });

    await eventually(() => expect(findings()).toHaveLength(2));

    const hash = navigation.hash();

    const clickPrevented = (selector: string) => {
      const event = new MouseEvent('click', { bubbles: true, cancelable: true });

      (document.querySelector(selector) as HTMLElement).dispatchEvent(event);

      return event.defaultPrevented;
    };

    expect(clickPrevented('[data-testid=finding] a[href="#notes"]')).toBe(true);

    await eventually(() => expect(all('[data-testid=reviewer-notes]')).toHaveLength(1));

    expect(clickPrevented('[data-testid=reviewer-notes] a[href="#more"]')).toBe(true);

    expect(clickPrevented('[data-testid=finding] a[href="https://example.test"]')).toBe(false);

    expect(navigation.hash()).toBe(hash);

    expect(isShown('[data-testid=round-overview]')).toBe(true);
  });
});

describe('round overview: notes', () => {
  it('shows what a file says besides its findings as a notes block of that reviewer, under All only', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.texts['review/round-1/review-security.md'] = `PASS ok\n- [Nit] a:1 - What: w. Why: y. Fix: f.\n\nChecked against the **spec**: layout and pins.\n${CLOSING}\n`;
    });

    await eventually(() => expect(all('[data-testid=reviewer-notes]')).toHaveLength(1));

    const notes = all('[data-testid=reviewer-notes]')[0];

    expect(notes.querySelector('h3')?.textContent).toBe('Notes from security');

    expect(notes.querySelector('strong')?.textContent).toBe('spec');

    expect(notes.textContent).toContain('layout and pins.');

    expect(cards()[1].querySelector('[data-testid=reviewer-other]')?.textContent).toBe('Also holds text that is not a finding: shown below the findings.');

    expect(text('[data-testid=round-summary]')).toContain('1 note');

    chips()[1].click();

    await eventually(() => expect(all('[data-testid=reviewer-notes]')).toHaveLength(0));

    chips()[0].click();

    await eventually(() => expect(all('[data-testid=reviewer-notes]')).toHaveLength(1));
  });

  it('says there are no finding cards, and points at the notes, when a file holds only text', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.detail = detailWithRounds({ column: 'Done', rounds: [{ n: 1, reviews: { code: 'PASS' } }], files: [reviewFile(1, 'code', 'PASS ok')] });

      client.texts['review/round-1/review-code.md'] = `PASS ok\n\nFree text only.\n${CLOSING}\n`;
    });

    await eventually(() => expect(text('[data-testid=findings-empty]')).toBe('No finding cards in this round. The notes of the reviewers are below.'));

    expect(text('[data-testid=reviewer-notes]')).toContain('Free text only.');

    expect(text('[data-testid=round-summary]')).toBe('The reviewer passed · 1 note');
  });
});

describe('round overview: the Round dropdown', () => {
  it('shows the round as the label of the button and lists every round with its outcome, the current one checked', async () => {
    await openOverview(1);

    expect(button().getAttribute('aria-haspopup')).toBe('listbox');

    expect(button().getAttribute('aria-expanded')).toBe('false');

    expect(text('[data-testid=round-picker]')).toContain('Round 1');

    expect(text('[data-testid=round-picker] .flex-col > span')).toBe('Round');

    expect(isShown('[data-testid=round-menu]')).toBe(false);

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    expect(button().getAttribute('aria-expanded')).toBe('true');

    expect(menuOptions().map((option) => option.textContent?.replace(/\s+/g, ' ').trim())).toEqual(['check Round 1 errorCHANGES', 'check Round 2 progress_activityRUNNING']);

    expect(menuOptions().map((option) => option.getAttribute('aria-selected'))).toEqual(['true', 'false']);

    expect(document.querySelector('#round-listbox')?.getAttribute('aria-label')).toBe('Round');

    expect(document.querySelector('[data-testid=round-menu] input')).toBeNull();

    await eventually(() => expect(document.activeElement).toBe(menuOptions()[0]));
  });

  it('opens the overview of the round it picks with the mouse, closes, and gives the focus back to the button', async () => {
    await openOverview(1);

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    menuOptions()[1].click();

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 2'));

    expect(navigation.hash()).toBe('#/task/demo/fix-export/round/2');

    expect(isShown('[data-testid=round-menu]')).toBe(false);

    expect(document.activeElement).toBe(button());

    expect(overviewRow(2).getAttribute('aria-current')).toBe('true');
  });

  it('picks with the keyboard: Arrow keys move, Enter and Space choose, Escape closes and refocuses', async () => {
    await openOverview(1);

    button().click();

    await eventually(() => expect(document.activeElement).toBe(menuOptions()[0]));

    press('ArrowDown', document.activeElement as HTMLElement);

    expect(document.activeElement).toBe(menuOptions()[1]);

    press('ArrowDown', document.activeElement as HTMLElement);

    expect(document.activeElement).toBe(menuOptions()[1]);

    press('ArrowUp', document.activeElement as HTMLElement);

    expect(document.activeElement).toBe(menuOptions()[0]);

    press('Escape', document.activeElement as HTMLElement);

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(false));

    expect(document.activeElement).toBe(button());

    expect(text('[data-testid=round-title]')).toBe('Round 1');

    button().click();

    await eventually(() => expect(document.activeElement).toBe(menuOptions()[0]));

    press('ArrowDown', document.activeElement as HTMLElement);

    press('Enter', document.activeElement as HTMLElement);

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 2'));

    button().click();

    await eventually(() => expect(document.activeElement).toBe(menuOptions()[1]));

    press('ArrowUp', document.activeElement as HTMLElement);

    press(' ', document.activeElement as HTMLElement);

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 1'));
  });

  it('closes when the focus leaves it or the page is clicked elsewhere, and picking the round already shown only closes', async () => {
    await openOverview(1);

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    // Alpine's .outside ignores an element without layout, and happy-dom has none
    Object.defineProperty(button().parentElement as HTMLElement, 'offsetWidth', { value: 300, configurable: true });

    document.body.click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(false));

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    const outside = document.querySelector('[data-testid=task-back]') as HTMLElement;

    menuOptions()[0].dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: menuOptions()[1] }));

    menuOptions()[0].dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: null }));

    await flush();

    expect(isShown('[data-testid=round-menu]')).toBe(true);

    menuOptions()[0].dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: outside }));

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(false));

    button().click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(true));

    const generation = taskClient.fileCalls.length;

    menuOptions()[0].click();

    await eventually(() => expect(isShown('[data-testid=round-menu]')).toBe(false));

    expect(taskClient.fileCalls.length).toBe(generation);

    expect(navigation.hash()).toBe('#/task/demo/fix-export/round/1');
  });
});

describe('round overview: a file that was read while it was being written', () => {
  const halfWritten = (state: 'pending' | 'PASS') => detailWithRounds({ rounds: [{ n: 1, reviews: { code: 'CHANGES', security: state } }] });

  it('reads the file again when the seat state changed, though the task changed within the same second', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.detail = halfWritten('pending');

      client.texts['review/round-1/review-security.md'] = 'PASS half';
    });

    await eventually(() => expect(cards()[1].querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('Has not reported yet.'));

    taskClient.texts['review/round-1/review-security.md'] = `PASS all done\n- [Nit] z:1 - What: w. Why: y. Fix: f.\n${CLOSING}\n`;

    taskClient.detail = halfWritten('PASS');

    pollAgain();

    await eventually(() => expect(cards()[1].querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('all done'));

    expect(cards()[1].querySelector('[data-testid=reviewer-counts]')?.textContent).toContain('0 important · 1 nit');
  });

  it('does not keep a file without its closing line, so the next poll reads it again', async () => {
    await mount('#/task/demo/fix-export/round/1', (client) => {
      client.detail = halfWritten('pending');

      client.texts['review/round-1/review-security.md'] = 'PASS half';
    });

    await eventually(() => expect(cards()).toHaveLength(2));

    const reads = () => taskClient.fileCalls.filter((path) => path === 'review/round-1/review-security.md').length;

    const before = reads();

    pollAgain();

    await eventually(() => expect(reads()).toBe(before + 1));

    pollAgain();

    await eventually(() => expect(reads()).toBe(before + 2));
  });
});

describe('round overview: data', () => {
  it('fetches the review files of the round once, in parallel, and again only when one changed', async () => {
    taskClient.fileCalls.length = 0;

    await openOverview(1);

    await eventually(() => expect(cards()).toHaveLength(2));

    expect(taskClient.fileCalls.filter((path) => path.startsWith('review/round-1/')).sort()).toEqual(['review/round-1/review-code.md', 'review/round-1/review-security.md']);

    taskClient.fileCalls.length = 0;

    pollAgain();

    await eventually(() => expect(taskClient.taskCalls).toBeGreaterThan(1));

    await flush();

    expect(taskClient.fileCalls).toEqual([]);

    taskClient.texts['review/round-1/review-security.md'] = `PASS changed\n${CLOSING}\n`;

    taskClient.detail = detailWithRounds({ updatedAt: '2026-11-24T09:05:00Z' });

    pollAgain();

    await eventually(() => expect(cards()[1].querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('changed'));
  });

  it('fills in a round as its reviewers report, without losing the filter or rebuilding the other cards', async () => {
    await openOverview(2);

    await eventually(() => expect(cards()).toHaveLength(2));

    chips()[2].click();

    const kept = cards()[0];

    taskClient.texts['review/round-2/review-code.md'] = ['CHANGES now done', '- [Important] q:1 - What: w. Why: y. Fix: f.', CLOSING, ''].join('\n');

    taskClient.detail = detailWithRounds({ updatedAt: '2026-11-24T09:10:00Z', rounds: [{ n: 1, reviews: { code: 'CHANGES', security: 'PASS' } }, { n: 2, reviews: { code: 'CHANGES', security: 'pending' } }] });

    pollAgain();

    await eventually(() => expect(text('[data-testid=round-status]')).toBe('errorCHANGES'));

    expect(cards()[0]).toBe(kept);

    expect(chips()[2].getAttribute('aria-pressed')).toBe('true');

    expect(chips().map((chip) => chip.textContent?.replace(/\s+/g, ' ').trim())).toEqual(['All 1', 'Important 1', 'Nits 0']);

    expect(findings()).toHaveLength(0);
  });

  it('ignores the answer for a round that was left before the answer arrived', async () => {
    taskClient.gated.add('review/round-1/review-code.md');

    taskClient.gated.add('review/round-1/review-security.md');

    all('.file')[0].click();

    roundToggle(1).click();

    await eventually(() => expect(overviewRow(1)).toBeDefined());

    overviewRow(1).click();

    await eventually(() => expect(text('[data-testid=round-loading]')).toBe('Loading the round…'));

    const page = (Alpine.$data(document.querySelector('[x-data]') as HTMLElement) as { taskPage: { roundChips: unknown[]; visibleFindings: unknown[]; visibleNotes: unknown[]; emptyFindingsMessage: string } }).taskPage;

    expect([page.roundChips, page.visibleFindings, page.visibleNotes, page.emptyFindingsMessage]).toEqual([[], [], [], '']);

    overviewRow(2).click();

    await eventually(() => expect(text('[data-testid=round-title]')).toBe('Round 2'));

    await eventually(() => expect(cards().map((card) => card.dataset.reviewer)).toEqual(['code', 'security']));

    taskClient.release();

    await flush();

    await flush();

    expect(text('[data-testid=round-title]')).toBe('Round 2');

    expect(text('[data-testid=round-status]')).toBe('progress_activityRUNNING');

    expect(cards()[0].querySelector('[data-testid=reviewer-headline]')?.textContent).toBe('Has not reported yet.');
  });

  it('ignores the answer that arrives after the task page was left', async () => {
    taskClient.gated.add('review/round-1/review-code.md');

    roundToggle(1).click();

    await eventually(() => expect(overviewRow(1)).toBeDefined());

    overviewRow(1).click();

    await eventually(() => expect(text('[data-testid=round-loading]')).toBe('Loading the round…'));

    (document.querySelector('[data-testid=task-back]') as HTMLElement).click();

    await eventually(() => expect(isShown('[data-testid=board]')).toBe(true));

    taskClient.release();

    await flush();

    await flush();

    expect(cards()).toHaveLength(0);
  });

  it('falls back to the first file when the round disappears from the task', async () => {
    await openOverview(2);

    taskClient.detail = detailWithRounds({ files: [{ path: 'spec.md', group: 'Job', firstLine: '# Spec', tone: null }], rounds: [] });

    pollAgain();

    await eventually(() => expect(isShown('[data-testid=round-overview]')).toBe(false));

    await eventually(() => expect(text('[data-testid=task-body]')).toContain('Hello'));
  });

  it('keeps one h1 and a heading order that does not skip a level', async () => {
    await openOverview(1);

    await eventually(() => expect(cards()).toHaveLength(2));

    expect(all('[data-testid=task-page] h1')).toHaveLength(1);

    const levels = all('[data-testid=round-overview] h2, [data-testid=round-overview] h3').map((heading) => heading.tagName);

    expect(levels[0]).toBe('H2');

    expect(levels.slice(1).every((level) => level === 'H3')).toBe(true);
  });
});
