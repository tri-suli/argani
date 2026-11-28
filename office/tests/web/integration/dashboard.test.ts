// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import type { PollHandlers, Poller } from '@/types/poller';
import BoardView from '@/board/board-view';
import createDashboard from '@/components/dashboard';
import { FakeTaskClient, sampleSnapshot, sampleTasks } from '../sample-snapshot';
import sampleMarkdownRenderer from '../sample-markdown-renderer';
import pageMarkup from './page-markup';
import eventually from './eventually';

class FakePoller implements Poller {
  handlers!: PollHandlers;

  stopped = false;

  start(handlers: PollHandlers) {
    this.handlers = handlers;
  }

  stop() {
    this.stopped = true;
  }
}

// Alpine renders nested x-for templates over several ticks, so assertions on rendered output retry with vi.waitFor.
const markdownRenderer = sampleMarkdownRenderer();

const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();

const visible = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';

const card = (task: string) => document.querySelector(`[data-task="${task}"]`) as HTMLElement;

const within = (task: string, selector: string) => card(task).querySelector(selector) as HTMLElement;

const showing = (element: Element | null) => (element as HTMLElement).style.display !== 'none';

let poller: FakePoller;

let taskClient: FakeTaskClient;

let clipboard: { writeText: Mock<(text: string) => Promise<void>> };

const now = () => new Date('2026-11-24T10:00:10Z');

beforeAll(() => {
  Alpine.data('dashboard', () => createDashboard({ poller, taskClient, boardView: new BoardView(), markdownRenderer, clipboard, now }));

  Alpine.start();
});

beforeEach(async () => {
  poller = new FakePoller();

  taskClient = new FakeTaskClient();

  clipboard = { writeText: vi.fn(async (_text: string) => {}) };

  document.body.innerHTML = pageMarkup();

  Alpine.initTree(document.body);

  await eventually(() => expect(poller.handlers).toBeDefined());
});

const deliver = async (snapshot = sampleSnapshot(), expectedCards = 3) => {
  poller.handlers.onSnapshot(snapshot, sampleTasks());

  await eventually(() => {
    expect(text('[data-testid=status]')).toBe('Connected');

    expect(document.querySelectorAll('.card')).toHaveLength(expectedCards);
  });
};

const all = (selector: string) => [...document.querySelectorAll(selector)].map((element) => element.textContent?.replace(/\s+/g, ' ').trim());

const click = (selector: string) => (document.querySelector(selector) as HTMLElement).click();

const menuOpen = () => visible('[data-testid=project-menu]');

const openMenu = async () => {
  click('[data-testid=project-picker]');

  await eventually(() => expect(menuOpen()).toBe(true));
};

const pressOn = (target: Element, key: string) => target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));

const option = (project: string) => document.querySelector(`[data-project="${project}"]`) as HTMLElement;

const cardKeys = () => [...document.querySelectorAll('.card')].map((element) => element.getAttribute('data-task'));

describe('dashboard board', () => {
  it('shows loading before the first snapshot', () => {
    expect(text('[data-testid=status]')).toBe('Connecting');

    expect(visible('[data-testid=loading]')).toBe(true);

    expect(document.querySelectorAll('.col')).toHaveLength(0);

    expect(document.querySelector('[data-testid=needs-human]')).toBeNull();
  });

  it('renders the header, five numbered columns with count badges, and no footer', async () => {
    await deliver();

    expect(text('h1')).toBe('Argani Office');

    expect(text('[data-testid=home]')).toBe('/home/user/.argani');

    expect(text('[data-testid=updated]')).toBe('· updated 0s ago');

    expect(all('.col-head')).toEqual(['01 Intake 1', '02 Spec 0', '03 Build 1', '04 Review 1', '05 Approve 0']);

    expect([...document.querySelectorAll('[data-testid=column-count]')].map((badge) => badge.getAttribute('title'))).toEqual(['intake', 'spec-writer', 'builder · verify', 'reviewers', 'approver · merge']);

    expect(document.querySelector('footer')).toBeNull();

    expect(visible('[data-testid=loading]')).toBe(false);
  });

  it('renders the four totals tiles', async () => {
    await deliver();

    expect(all('[data-tile]')).toEqual([
      'Agents working 1 builder',
      'Waiting for you 40m 2 tasks',
      'Tokens 1.2M across 5 open tasks',
      'Manual acceptance criteria 3 to check by hand before merge',
    ]);

    expect(document.querySelector('[data-tile=waiting] [data-testid=tile-value]')?.getAttribute('data-tone')).toBe('human');
  });

  it('lists the tasks in Needs human with reason, wait, visits, question and the answer command', async () => {
    await deliver();

    expect(text('[data-testid=needs-human-count]')).toBe('2');

    expect(all('[data-testid=needs-human-row]').length).toBe(2);

    const [stuck, blocked] = [...document.querySelectorAll('[data-testid=needs-human-row]')];

    expect(stuck.getAttribute('data-row')).toBe('demo/stuck');

    expect(stuck.querySelector('p')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('demo · manual verification · waiting 40m · 2× you');

    expect(text('[data-row="demo/stuck"] [data-testid=row-title]')).toBe('Stuck task');

    expect(text('[data-row="demo/stuck"] [data-testid=row-question]')).toBe('decide the schema');

    expect(text('[data-row="demo/stuck"] [data-testid=row-command]')).toBe('/argani:factory answer stuck <answer>');

    expect(blocked.getAttribute('data-row')).toBe('other/blocked');

    expect(text('[data-row="other/blocked"] [data-testid=row-question]')).toBe('tasks.json is unreadable');

    expect(showing(blocked.querySelector('[data-testid=row-waiting]'))).toBe(false);

    expect(showing(blocked.querySelector('[data-testid=row-visits]'))).toBe(false);
  });

  it('removes the Needs human panel when no task waits for you', async () => {
    await deliver();

    await deliver(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }] }), 0);

    await eventually(() => expect(document.querySelector('[data-testid=needs-human]')).toBeNull());
  });

  it('copies the answer command and says Copied, then Copy failed when the clipboard refuses', async () => {
    await deliver();

    const copy = '[data-row="demo/stuck"] [data-testid=row-copy]';

    expect(text(copy)).toBe('Copy');

    click(copy);

    await eventually(() => expect(text(copy)).toBe('Copied'));

    expect(clipboard.writeText).toHaveBeenCalledWith('/argani:factory answer stuck <answer>');

    expect(text('[data-row="other/blocked"] [data-testid=row-copy]')).toBe('Copy');

    clipboard.writeText.mockRejectedValueOnce(new Error('denied'));

    click(copy);

    await eventually(() => expect(text(copy)).toBe('Copy failed'));
  });

  it('opens the task drawer from the title of a Needs human row and returns the focus to it', async () => {
    await deliver();

    click('[data-row="demo/stuck"] [data-testid=row-title]');

    await eventually(() => expect(visible('[data-testid=drawer]')).toBe(true));

    expect(text('[data-testid=drawer-title]')).toBe('Stuck task');

    pressOn(document.body, 'Escape');

    await eventually(() => expect(document.activeElement).toBe(document.querySelector('[data-row="demo/stuck"] [data-testid=row-title]')));
  });

  it('lists the Done tasks newest first, with cancelled ones struck through', async () => {
    await deliver();

    expect(text('[data-testid=done-count]')).toBe('2');

    expect(all('[data-testid=done-title]')).toEqual(['Dropped idea', 'Ship it']);

    expect(all('[data-testid=done-outcome]')).toEqual(['block cancelled', 'merge merged']);

    expect(all('[data-testid=done-time]')[1]).toBe('· 1h05m');

    const [dropped, shipped] = [...document.querySelectorAll('[data-testid=done-row]')];

    expect(dropped.querySelector('[data-testid=done-title]')?.getAttribute('data-cancelled')).toBe('true');

    expect(shipped.querySelector('[data-testid=done-title]')?.hasAttribute('data-cancelled')).toBe(false);

    expect(showing(dropped.querySelector('[data-testid=done-time]'))).toBe(false);

    (shipped.querySelector('[data-testid=done-title]') as HTMLElement).click();

    await eventually(() => expect(text('[data-testid=drawer-title]')).toBe('Ship it'));
  });

  it('renders card details: working row, chips with icons, risk, time, tokens, MR link', async () => {
    await deliver();

    await eventually(() => {
      const fix = '[data-task="demo/fix-export"]';

      expect(card('demo/fix-export').getAttribute('data-active')).toBe('true');

      expect(all(`${fix} [data-testid=card-working]`)).toEqual(['Agent working: builder · 10s']);

      expect(document.querySelectorAll('[data-testid=card-working]')).toHaveLength(1);

      expect(text(`${fix} [data-testid=card-project]`)).toBe('demo');

      expect(text(`${fix} [data-testid=card-slug]`)).toBe('fix-export');

      expect(text(`${fix} .feature`)).toBe('Fix export');

      expect(text(`${fix} .round`)).toContain('R1');

      expect([...card('demo/fix-export').querySelectorAll('.chip')].map((chip) => [chip.getAttribute('data-state'), chip.textContent?.replace(/\s+/g, ' ').trim()])).toEqual([
        ['PASS', 'checkcode: PASS'],
        ['wait', 'hourglass_topcompliance: pending'],
      ]);

      expect(text(`${fix} [data-testid=card-risk]`)).toBe('medium');

      expect(within('demo/fix-export', '[data-testid=card-risk]').parentElement?.getAttribute('data-risk')).toBe('medium');

      expect(text(`${fix} [data-testid=card-time]`)).toBe('2m');

      expect(text(`${fix} [data-testid=card-tokens]`)).toBe('48.2k tok');

      const link = within('demo/fix-export', 'a');

      expect(link.getAttribute('href')).toBe('https://example.test/mr/7');

      expect(link.getAttribute('target')).toBe('_blank');

      expect(showing(within('demo/add-login', '[data-testid=card-time]'))).toBe(false);

      expect(showing(within('demo/add-login', '[data-testid=card-mr]'))).toBe(false);

      expect(showing(within('demo/add-login', '[data-testid=card-risk]').parentElement)).toBe(false);

      expect(card('demo/add-login').querySelectorAll('[data-testid=card-working]')).toHaveLength(0);
    });
  });

  it('gives each card the button role and an accessible name', async () => {
    await deliver();

    await eventually(() => {
      expect(card('demo/fix-export').getAttribute('role')).toBe('button');

      expect(card('demo/fix-export').getAttribute('aria-label')).toBe('Fix export, demo fix-export');
    });
  });

  it('keeps Needs human and Done tasks out of the pipeline', async () => {
    await deliver();

    expect(cardKeys()).toEqual(['demo/add-login', 'demo/fix-export', 'demo/older']);

    expect([...document.querySelectorAll('[data-column="Build"] .card')].map((element) => element.getAttribute('data-task'))).toEqual(['demo/fix-export']);
  });

  it('shows empty states and zero tiles', async () => {
    await deliver(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }], agents: [] }), 0);

    await eventually(() => {
      expect(document.querySelectorAll('.col .empty:not([style*="none"])')).toHaveLength(5);

      expect(text('[data-testid=done-rail]')).toContain('Nothing here');

      expect(text('[data-tile=agents]')).toBe('Agents working 0 —');

      expect(text('[data-tile=waiting]')).toBe('Waiting for you — 0 tasks');
    });
  });

  it('opens and closes the project picker, listing every project with its counts', async () => {
    await deliver();

    expect(menuOpen()).toBe(false);

    expect(text('[data-testid=project-name]')).toBe('All projects');

    expect(text('[data-testid=project-count]')).toBe('7');

    const picker = document.querySelector('[data-testid=project-picker]') as HTMLElement;

    expect([picker.getAttribute('aria-haspopup'), picker.getAttribute('aria-expanded')]).toEqual(['listbox', 'false']);

    await openMenu();

    expect(picker.getAttribute('aria-expanded')).toBe('true');

    expect(all('[data-testid=project-option-name]')).toEqual(['All projects', 'demo', 'other']);

    expect(all('[data-testid=project-option-count]')).toEqual(['Tasks: 7', 'Tasks: 4', 'Tasks: 3']);

    expect([...document.querySelectorAll('[role=option]')].map((element) => element.getAttribute('aria-selected'))).toEqual(['true', 'false', 'false']);

    expect(all('[data-testid=project-option-waiting]')).toEqual(['person_raised_hand2 in Needs human', 'person_raised_hand1 in Needs human', 'person_raised_hand1 in Needs human']);

    await eventually(() => expect(document.activeElement).toBe(document.querySelector('[data-testid=project-search]')));
  });

  it('hides the waiting count of a project with nothing in Needs human', async () => {
    await deliver(sampleSnapshot({ projects: [{ name: 'demo', tasks: sampleSnapshot().projects[0].tasks.slice(0, 2) }] }), 2);

    await openMenu();

    expect([...document.querySelectorAll('[data-testid=project-option-waiting]')].map((element) => showing(element))).toEqual([false, false]);
  });

  it('filters the board to the picked project and closes the picker with the focus on its button', async () => {
    await deliver();

    await openMenu();

    option('other').click();

    await eventually(() => {
      expect(cardKeys()).toEqual([]);

      expect(menuOpen()).toBe(false);

      expect(text('[data-testid=project-name]')).toBe('other');

      expect(text('[data-testid=project-count]')).toBe('3');

      expect(document.querySelectorAll('[data-testid=done-row]')).toHaveLength(2);

      expect(text('[data-tile=agents]')).toBe('Agents working 0 —');

      expect(document.activeElement).toBe(document.querySelector('[data-testid=project-picker]'));
    });

    await openMenu();

    option('demo').click();

    await eventually(() => expect(cardKeys()).toEqual(['demo/add-login', 'demo/fix-export', 'demo/older']));
  });

  it('searches the project list by name, ignoring case', async () => {
    await deliver();

    await openMenu();

    const search = document.querySelector('[data-testid=project-search]') as HTMLInputElement;

    search.value = 'OTH';

    search.dispatchEvent(new Event('input'));

    await eventually(() => expect(all('[data-testid=project-option-name]')).toEqual(['other']));

    expect(visible('[data-testid=project-empty]')).toBe(false);

    search.value = 'nothing';

    search.dispatchEvent(new Event('input'));

    await eventually(() => {
      expect(document.querySelectorAll('[role=option]')).toHaveLength(0);

      expect(visible('[data-testid=project-empty]')).toBe(true);
    });
  });

  it('closes on Escape back to the button, and on a click outside', async () => {
    await deliver();

    await openMenu();

    pressOn(document.querySelector('[data-testid=project-search]') as Element, 'Escape');

    await eventually(() => {
      expect(menuOpen()).toBe(false);

      expect(document.activeElement).toBe(document.querySelector('[data-testid=project-picker]'));
    });

    await openMenu();

    // Alpine's .outside ignores an element without layout, and happy-dom has none
    Object.defineProperty((document.querySelector('[data-testid=project-picker]') as HTMLElement).parentElement, 'offsetWidth', { value: 300 });

    document.body.click();

    await eventually(() => expect(menuOpen()).toBe(false));
  });

  it('moves between the options with the arrow keys and picks with Enter and Space', async () => {
    await deliver();

    await openMenu();

    const search = document.querySelector('[data-testid=project-search]') as HTMLElement;

    search.focus();

    pressOn(search, 'ArrowDown');

    expect(document.activeElement).toBe(option(''));

    pressOn(document.activeElement as Element, 'ArrowDown');

    expect(document.activeElement).toBe(option('demo'));

    pressOn(document.activeElement as Element, 'Enter');

    await eventually(() => {
      expect(text('[data-testid=project-name]')).toBe('demo');

      expect(menuOpen()).toBe(false);
    });

    await openMenu();

    pressOn(option('other'), ' ');

    await eventually(() => expect(text('[data-testid=project-name]')).toBe('other'));
  });

  it('resets the project filter when the selected project disappears', async () => {
    await deliver();

    await openMenu();

    option('other').click();

    await eventually(() => expect(text('[data-testid=project-name]')).toBe('other'));

    await deliver(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }] }), 0);

    await eventually(() => expect(text('[data-testid=project-name]')).toBe('All projects'));
  });

  it('keeps the last data and shows a banner when a poll fails, then recovers', async () => {
    await deliver();

    poller.handlers.onError(new Error('backend down'));

    await eventually(() => {
      expect(visible('[data-testid=error-banner]')).toBe(true);

      expect(text('[data-testid=error-banner]')).toContain('backend down');

      expect(text('[data-testid=error-banner]')).toContain('2026-11-24T10:00:10.000Z');

      expect(text('[data-testid=status]')).toBe('Disconnected');

      expect(text('[data-testid=status-error]')).toBe('· backend down');

      expect(document.querySelectorAll('.card')).toHaveLength(3);
    });

    await deliver();

    await eventually(() => expect(visible('[data-testid=error-banner]')).toBe(false));
  });

  it('shows the failure without data when the first poll fails', async () => {
    poller.handlers.onError(new Error('never up'));

    await eventually(() => {
      expect(text('[data-testid=error-banner]')).toContain('never up');

      expect(visible('[data-testid=loading]')).toBe(false);
    });
  });

  it('counts the seconds since the last good poll every second, then minutes', () => {
    vi.useFakeTimers();

    try {
      let clock = Date.parse('2026-11-24T10:00:00Z');

      const handlers: PollHandlers[] = [];

      const ticking = createDashboard({ poller: { start: (h) => handlers.push(h), stop: () => {} }, taskClient, boardView: new BoardView(), markdownRenderer, clipboard, now: () => new Date(clock) });

      ticking.init();

      handlers[0].onSnapshot(sampleSnapshot(), sampleTasks());

      expect(ticking.updatedLabel).toBe('updated 0s ago');

      clock += 3000;

      vi.advanceTimersByTime(3000);

      expect(ticking.updatedLabel).toBe('updated 3s ago');

      clock += 87_000;

      vi.advanceTimersByTime(87_000);

      expect(ticking.updatedLabel).toBe('updated 1m ago');

      handlers[0].onSnapshot(sampleSnapshot(), sampleTasks());

      expect(ticking.updatedLabel).toBe('updated 0s ago');

      ticking.destroy();

      clock += 5000;

      vi.advanceTimersByTime(5000);

      expect(ticking.updatedLabel).toBe('updated 0s ago');
    } finally {
      vi.useRealTimers();
    }
  });

  it('stops polling when destroyed and has empty derived state before data', () => {
    const dashboard = createDashboard({ poller, taskClient, boardView: new BoardView(), markdownRenderer, clipboard, now: vi.fn() });

    expect(dashboard.projectOptions).toEqual([]);

    expect(dashboard.selectedOption.label).toBe('All projects');

    expect(dashboard.columns).toEqual([]);

    expect([dashboard.tiles, dashboard.needsHumanRows, dashboard.doneRows]).toEqual([[], [], []]);

    expect(dashboard.updatedLabel).toBe('');

    dashboard.destroy();

    expect(poller.stopped).toBe(true);
  });
});

describe('drawer history and metrics', () => {
  const openStuck = async () => {
    await deliver();

    await (card('demo/stuck') as HTMLElement).click();
  };

  it('lists the durations in order and the three metrics of the open task', async () => {
    await openStuck();

    await eventually(() => {
      expect([...document.querySelectorAll('[data-testid=history-row]')].map((row) => [...row.children].map((cell) => cell.textContent))).toEqual([['Build', '1h00m'], ['Needs human', '10m'], ['Build', '10m'], ['Needs human', '15m']]);

      expect(showing(document.querySelector('[data-testid=history-empty]'))).toBe(false);

      expect(text('[data-testid=drawer-metrics]')).toBe('2 manual ACs 2× in Needs human 25m waiting for you');
    });
  });

  it('shows a dash for a task without history', async () => {
    await deliver();

    await (card('demo/fix-export') as HTMLElement).click();

    await eventually(() => {
      expect(document.querySelectorAll('[data-testid=history-row]')).toHaveLength(0);

      expect(text('[data-testid=history-empty]')).toBe('—');

      expect(text('[data-testid=drawer-metrics]')).toBe('0 manual ACs 0× in Needs human 0m waiting for you');
    });
  });
});
