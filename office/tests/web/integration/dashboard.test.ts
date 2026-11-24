// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PollHandlers, Poller } from '../../../src/board/board-poller';
import { createDashboard } from '../../../src/components/dashboard';
import { sampleSnapshot } from '../sample-snapshot';
import { pageMarkup } from './page-markup';

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

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();
const visible = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';

let poller: FakePoller;

beforeAll(() => {
  Alpine.data('dashboard', () => createDashboard({ poller, now: () => new Date('2026-11-24T10:00:10Z') }));
  Alpine.start();
});

beforeEach(async () => {
  poller = new FakePoller();
  document.body.innerHTML = pageMarkup();
  Alpine.initTree(document.body);
  await settle();
});

describe('dashboard', () => {
  it('shows loading before the first snapshot', () => {
    expect(text('[data-testid=status]')).toBe('Connecting');
    expect(visible('[data-testid=loading]')).toBe(true);
    expect(document.querySelectorAll('.column')).toHaveLength(0);
  });

  it('renders columns, cards, agents and the marker', async () => {
    poller.handlers.onSnapshot(sampleSnapshot());
    await settle();
    expect(text('[data-testid=status]')).toBe('Connected');
    expect(text('[data-testid=home]')).toBe('/home/user/.argani');
    expect(text('[data-testid=generated-at]')).toBe('2026-11-24T10:00:05Z');
    expect([...document.querySelectorAll('.column h2')].map((heading) => heading.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
      'Backlog 1',
      'In progress 1',
      'Done 1',
    ]);
    const cardSelector = '[data-task="demo/fix-export"]';
    const card = () => document.querySelector(cardSelector) as HTMLElement;
    expect(card().textContent).toContain('Fix export');
    expect(card().textContent).toContain('Stage: spec');
    expect(card().textContent).toContain('Next: build');
    await settle();
    expect(card().getAttribute('data-active')).toBe('true');
    expect(card().querySelector<HTMLElement>('[data-testid=agent-marker]')?.style.display).not.toBe('none');
    expect(document.querySelector<HTMLElement>('[data-task="demo/add-login"] [data-testid=agent-marker]')?.style.display).toBe('none');
    expect(text('[data-testid=agent-item]')).toContain('argani:builder demo/fix-export sonnet');
    expect(visible('[data-testid=loading]')).toBe(false);
  });

  it('shows empty states and agents without slug or model', async () => {
    const [agent] = sampleSnapshot().agents;
    poller.handlers.onSnapshot(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }], agents: [{ ...agent, slug: null, model: undefined }] }));
    await settle();
    expect(document.querySelectorAll('.column .empty:not([style*="none"])')).toHaveLength(3);
    expect(text('[data-testid=agent-item]')).toContain('argani:builder demo');
    poller.handlers.onSnapshot(sampleSnapshot({ agents: [] }));
    await settle();
    expect(document.querySelector('[data-testid=agent-item]')).toBeNull();
    expect(text('.agents .empty')).toBe('No active agents');
  });

  it('filters by project', async () => {
    poller.handlers.onSnapshot(sampleSnapshot());
    await settle();
    expect([...document.querySelectorAll('[data-testid=project-filter] option')].map((option) => option.textContent)).toEqual(['All projects', 'demo', 'other']);
    const select = document.querySelector('[data-testid=project-filter]') as HTMLSelectElement;
    select.value = 'other';
    select.dispatchEvent(new Event('change'));
    await settle();
    expect([...document.querySelectorAll('.card')].map((card) => card.getAttribute('data-task'))).toEqual(['other/ship']);
  });

  it('resets the project filter when the selected project disappears', async () => {
    poller.handlers.onSnapshot(sampleSnapshot());
    await settle();
    const select = document.querySelector('[data-testid=project-filter]') as HTMLSelectElement;
    select.value = 'other';
    select.dispatchEvent(new Event('change'));
    await settle();
    poller.handlers.onSnapshot(sampleSnapshot({ projects: [{ name: 'demo', tasks: [] }] }));
    await settle();
    expect(select.value).toBe('');
  });

  it('keeps the last data and shows a banner when a poll fails, then recovers', async () => {
    poller.handlers.onSnapshot(sampleSnapshot());
    await settle();
    poller.handlers.onError(new Error('backend down'));
    await settle();
    expect(visible('[data-testid=error-banner]')).toBe(true);
    expect(text('[data-testid=error-banner]')).toContain('backend down');
    expect(text('[data-testid=error-banner]')).toContain('2026-11-24T10:00:10.000Z');
    expect(text('[data-testid=status]')).toBe('Disconnected');
    expect(document.querySelectorAll('.card')).toHaveLength(3);
    poller.handlers.onSnapshot(sampleSnapshot());
    await settle();
    expect(visible('[data-testid=error-banner]')).toBe(false);
    expect(text('[data-testid=status]')).toBe('Connected');
  });

  it('shows the failure without data when the first poll fails', async () => {
    poller.handlers.onError(new Error('never up'));
    await settle();
    expect(text('[data-testid=error-banner]')).toContain('never up');
    expect(visible('[data-testid=loading]')).toBe(false);
  });

  it('stops polling when destroyed', () => {
    const dashboard = createDashboard({ poller, now: vi.fn() });
    expect(dashboard.isActive(sampleSnapshot().projects[0].tasks[0])).toBe(false);
    expect(dashboard.projects).toEqual([]);
    expect(dashboard.agents).toEqual([]);
    dashboard.destroy();
    expect(poller.stopped).toBe(true);
  });
});
