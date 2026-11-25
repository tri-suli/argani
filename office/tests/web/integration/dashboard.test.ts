// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PollHandlers, Poller } from '@/board/types';
import BoardView from '@/board/board-view';
import createDashboard from '@/components/dashboard';
import { FakeTaskClient, sampleSnapshot, sampleTasks } from '../sample-snapshot';
import pageMarkup from './page-markup';

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
const eventually = (assertions: () => void) => vi.waitFor(assertions);
const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();
const visible = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';
const card = (task: string) => document.querySelector(`[data-task="${task}"]`) as HTMLElement;
const within = (task: string, selector: string) => card(task).querySelector(selector) as HTMLElement;
const showing = (element: Element | null) => (element as HTMLElement).style.display !== 'none';

let poller: FakePoller;
let taskClient: FakeTaskClient;
const now = () => new Date('2026-11-24T10:00:10Z');

beforeAll(() => {
  Alpine.data('dashboard', () => createDashboard({ poller, taskClient, boardView: new BoardView(), now }));
  Alpine.start();
});

beforeEach(async () => {
  poller = new FakePoller();
  taskClient = new FakeTaskClient();
  document.body.innerHTML = pageMarkup();
  Alpine.initTree(document.body);
  await eventually(() => expect(poller.handlers).toBeDefined());
});

const deliver = async (snapshot = sampleSnapshot(), expectedCards = 5) => {
  poller.handlers.onSnapshot(snapshot, sampleTasks());
  await eventually(() => {
    expect(text('[data-testid=status]')).toBe('Connected');
    expect(document.querySelectorAll('.card')).toHaveLength(expectedCards);
  });
};

describe('dashboard board', () => {
  it('shows loading before the first snapshot', () => {
    expect(text('[data-testid=status]')).toBe('Connecting');
    expect(visible('[data-testid=loading]')).toBe(true);
    expect(document.querySelectorAll('.col')).toHaveLength(0);
  });

  it('renders header, columns with who labels, and the footer', async () => {
    await deliver();
    expect(text('[data-testid=status]')).toBe('Connected');
    expect(text('[data-testid=home]')).toBe('/home/user/.argani');
    expect(text('[data-testid=updated]')).toBe('· updated 0s ago');
    expect([...document.querySelectorAll('.col-head')].map((head) => head.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
      'Intake 1 intent · you approve',
      'Spec 0 spec-writer',
      'Build 1 builder · verify',
      'Review 1 reviewers',
      'Approve 0 approver · you merge',
      'Needs human 1 you',
      'Done 1 merged',
    ]);
    expect(document.querySelector('[data-column="Needs human"]')?.getAttribute('data-tone')).toBe('human');
    expect(document.querySelector('[data-column="Done"]')?.getAttribute('data-tone')).toBe('merged');
    expect(text('[data-testid=totals]')).toBe('1 agents running · 1.2M tokens');
    expect(visible('[data-testid=loading]')).toBe(false);
  });

  it('renders card details: pulse, chips, risk, time, tokens, MR link', async () => {
    await deliver();
    await eventually(() => {
      const fix = '[data-task="demo/fix-export"]';
      expect(card('demo/fix-export').getAttribute('data-active')).toBe('true');
      expect(showing(within('demo/fix-export', '[data-testid=agent-marker]'))).toBe(true);
      expect(showing(within('demo/add-login', '[data-testid=agent-marker]'))).toBe(false);
      expect(text(`${fix} .num`)).toBe('demo · fix-export');
      expect(text(`${fix} .feature`)).toBe('Fix export');
      expect(text(`${fix} .round`)).toContain('R1');
      expect([...card('demo/fix-export').querySelectorAll('.chip')].map((chip) => chip.getAttribute('data-state'))).toEqual(['PASS', 'wait']);
      expect(text(`${fix} [data-testid=card-risk]`)).toBe('medium');
      expect(within('demo/fix-export', '[data-testid=card-risk]').getAttribute('data-risk')).toBe('medium');
      expect(text(`${fix} [data-testid=card-time]`)).toBe('2m');
      expect(text(`${fix} [data-testid=card-tokens]`)).toBe('48.2k tok');
      const link = within('demo/fix-export', 'a');
      expect(link.getAttribute('href')).toBe('https://example.test/mr/7');
      expect(link.getAttribute('target')).toBe('_blank');
      expect(showing(within('demo/add-login', '[data-testid=card-time]'))).toBe(false);
      expect(showing(within('demo/add-login', '[data-testid=card-links]'))).toBe(false);
    
    });
  });

  it('gives each card the button role and an accessible name', async () => {
    await deliver();
    await eventually(() => {
      expect(card('demo/fix-export').getAttribute('role')).toBe('button');
      expect(card('demo/fix-export').getAttribute('aria-label')).toBe('Fix export, demo fix-export');
    });
  });

  it('flags and hints the cards waiting for the human, dims Done cards, sorts newest first', async () => {
    await deliver();
    expect(text('[data-task="demo/stuck"] [data-testid=card-flag]')).toBe('your call');
    expect(text('[data-task="demo/stuck"] [data-testid=card-hint]')).toBe('decide the schema');
    expect(card('demo/stuck').getAttribute('data-flagged')).toBe('true');
    expect(card('demo/fix-export').hasAttribute('data-flagged')).toBe(false);
    expect(text('[data-task="demo/add-login"] [data-testid=card-flag]')).toBe('your call');
    expect(text('[data-task="demo/add-login"] [data-testid=card-hint]')).toBe('approve intent');
    expect(showing(within('demo/fix-export', '[data-testid=card-flag]'))).toBe(false);
    expect(card('other/ship').getAttribute('data-dimmed')).toBe('true');
    expect([...document.querySelectorAll('[data-column="Build"] .card')].map((element) => element.getAttribute('data-task'))).toEqual(['demo/fix-export']);
  });

  it('shows empty states and agents running as zero', async () => {
    await deliver(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }], agents: [] }), 0);
    await eventually(() => {
      expect(document.querySelectorAll('.col .empty:not([style*="none"])')).toHaveLength(7);
      expect(text('[data-testid=totals]')).toContain('0 agents running');
    });
  });

  it('filters by project', async () => {
    await deliver();
    expect([...document.querySelectorAll('[data-testid=project-filter] option')].map((option) => option.textContent)).toEqual(['All projects', 'demo', 'other']);
    const select = document.querySelector('[data-testid=project-filter]') as HTMLSelectElement;
    select.value = 'other';
    select.dispatchEvent(new Event('change'));
    await eventually(() => expect([...document.querySelectorAll('.card')].map((element) => element.getAttribute('data-task'))).toEqual(['other/ship']));
  });

  it('resets the project filter when the selected project disappears', async () => {
    await deliver();
    const select = document.querySelector('[data-testid=project-filter]') as HTMLSelectElement;
    select.value = 'other';
    select.dispatchEvent(new Event('change'));
    await eventually(() => expect(document.querySelectorAll('.card')).toHaveLength(1));
    await deliver(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }] }), 0);
    await eventually(() => expect(select.value).toBe(''));
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
      expect(document.querySelectorAll('.card')).toHaveLength(5);
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
      const ticking = createDashboard({ poller: { start: (h) => handlers.push(h), stop: () => {} }, taskClient, boardView: new BoardView(), now: () => new Date(clock) });
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
    const dashboard = createDashboard({ poller, taskClient, boardView: new BoardView(), now: vi.fn() });
    expect(dashboard.projects).toEqual([]);
    expect(dashboard.columns).toEqual([]);
    expect(dashboard.agentsRunning).toBe(0);
    expect(dashboard.updatedLabel).toBe('');
    dashboard.destroy();
    expect(poller.stopped).toBe(true);
  });
});
