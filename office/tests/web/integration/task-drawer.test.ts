// @vitest-environment happy-dom
import Alpine from 'alpinejs';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PollHandlers, Poller } from '../../../src/board/types';
import { createDashboard } from '../../../src/components/dashboard';
import { createTaskDrawer } from '../../../src/components/task-drawer';
import type { FileTone } from '../../../src/board/types';
import { FakeTaskClient, sampleDetail, sampleSnapshot, sampleTasks } from '../sample-snapshot';
import { pageMarkup } from './page-markup';

class FakePoller implements Poller {
  handlers!: PollHandlers;
  start(handlers: PollHandlers) {
    this.handlers = handlers;
  }
  stop() {}
}

// Alpine renders nested x-for templates over several ticks, so assertions on rendered output retry with vi.waitFor;
// "nothing happened" assertions first let Alpine and the pending promises flush with Alpine.nextTick().
const eventually = (assertions: () => void) => vi.waitFor(assertions);
const flush = () => Alpine.nextTick();
const text = (selector: string) => document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();
const isShown = (selector: string) => (document.querySelector(selector) as HTMLElement).style.display !== 'none';
const card = () => document.querySelector('[data-task="demo/fix-export"]') as HTMLElement;
const fileButtons = () => [...document.querySelectorAll<HTMLElement>('.file')];
const pageContent = () => [...document.querySelectorAll('.page > :not(.drawer-root)')];
const press = (key: string, init: KeyboardEventInit = {}, target: EventTarget = document.body) =>
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init }));
const openDrawer = async () => {
  card().click();
  await eventually(() => {
    expect(text('[data-testid=drawer-body]')).toContain('Hello');
    expect(fileButtons()).toHaveLength(3);
  });
};
const selectFile = (index: number) => fileButtons()[index].click();
const pollAgain = () => poller.handlers.onSnapshot(sampleSnapshot(), sampleTasks());

let poller: FakePoller;
let taskClient: FakeTaskClient;

beforeAll(() => {
  Alpine.data('dashboard', () => createDashboard({ poller, taskClient, now: () => new Date() }));
  Alpine.start();
});

beforeEach(async () => {
  poller = new FakePoller();
  taskClient = new FakeTaskClient();
  document.body.innerHTML = pageMarkup();
  Alpine.initTree(document.body);
  await eventually(() => expect(poller.handlers).toBeDefined());
  pollAgain();
  await eventually(() => expect(card()).not.toBeNull());
});

describe('task drawer', () => {
  it('is closed until a card is opened', () => {
    expect(isShown('[data-testid=drawer]')).toBe(false);
    expect(pageContent().some((element) => element.hasAttribute('inert'))).toBe(false);
  });

  it('opens on click with a dialog, headline, files, focus inside, first file selected', async () => {
    await openDrawer();
    expect(isShown('[data-testid=drawer]')).toBe(true);
    const dialog = document.querySelector('[role=dialog]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(text('[data-testid=drawer-title]')).toBe('Fix export');
    expect(text('[data-testid=drawer-headline]')).toBe('demo · fix-export · build · round 1 · medium · 2m · 6.0k tok');
    expect([...document.querySelectorAll('[data-testid=file-group]')].map((group) => group.textContent)).toEqual(['Job', 'Round 1']);
    expect(fileButtons().map((button) => button.querySelector('span:nth-child(2)')?.textContent)).toEqual(['spec.md', 'build.diff', 'review-code.md']);
    expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');
    expect(fileButtons()[2].querySelector('[data-testid=file-tone]')?.getAttribute('data-tone') === 'good').toBe(true);
    await eventually(() => expect(document.activeElement).toBe(document.querySelector('.close')));
  });

  it('names the tone of a file for screen readers, and nothing for a file without tone', async () => {
    await openDrawer();
    expect(fileButtons().map((button) => button.querySelector('.sr-only')?.textContent)).toEqual(['', '', ': passed']);
  });

  it('labels every tone', () => {
    const drawer = createTaskDrawer(taskClient);
    expect(['good', 'warn', 'stop', null].map((tone) => drawer.toneLabel(tone as FileTone | null))).toEqual(
      ['passed', 'changes requested', 'escalated', '']);
  });

  it('makes the page behind the drawer inert while it is open, and only then', async () => {
    await openDrawer();
    expect(pageContent().length).toBeGreaterThan(0);
    expect(pageContent().every((element) => element.hasAttribute('inert'))).toBe(true);
    expect(document.querySelector('.drawer-root')?.hasAttribute('inert')).toBe(false);
    press('Escape');
    await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(false));
    expect(pageContent().some((element) => element.hasAttribute('inert'))).toBe(false);
  });

  it('opens with Enter and Space on the card but not from the MR link', async () => {
    press('Enter', {}, card());
    await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(true));
    press('Escape');
    await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(false));
    press(' ', {}, card());
    await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(true));
    press('Escape');
    await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(false));
    const callsBefore = taskClient.taskCalls;
    press('Enter', {}, card().querySelector('a') as HTMLElement);
    await flush();
    expect(taskClient.taskCalls).toBe(callsBefore);
    expect(isShown('[data-testid=drawer]')).toBe(false);
  });

  it('does not open the drawer when the MR link is clicked', async () => {
    const link = card().querySelector('a') as HTMLElement;
    // keep happy-dom from opening the external URL; the app's own handlers still run
    link.addEventListener('click', (event) => event.preventDefault());
    link.click();
    await flush();
    expect(taskClient.taskCalls).toBe(0);
    expect(isShown('[data-testid=drawer]')).toBe(false);
  });

  it('closes with Escape, the scrim and the close button, and returns focus to the card', async () => {
    for (const close of [() => press('Escape'), () => (document.querySelector('[data-testid=scrim]') as HTMLElement).click(), () => (document.querySelector('.close') as HTMLElement).click()]) {
      card().click();
      await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(true));
      close();
      await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(false));
      await eventually(() => expect(document.activeElement).toBe(card()));
    }
  });

  it('ignores Escape while closed', async () => {
    press('Escape');
    await flush();
    expect(isShown('[data-testid=drawer]')).toBe(false);
  });

  it('keeps Tab inside the dialog', async () => {
    await openDrawer();
    const dialog = document.querySelector('[role=dialog]') as HTMLElement;
    const focusable = dialog.querySelectorAll<HTMLElement>('button, a[href]');
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    last.focus();
    press('Tab', {}, last);
    expect(document.activeElement).toBe(first);
    press('Tab', { shiftKey: true }, first);
    expect(document.activeElement).toBe(last);
    fileButtons()[1].focus();
    press('Tab', {}, fileButtons()[1]);
    expect(document.activeElement).toBe(fileButtons()[1]);
  });

  it('switches files; diffs and other files show as plain text, markdown with verdict and summary', async () => {
    await openDrawer();
    selectFile(1);
    await eventually(() => {
      expect(isShown('[data-testid=drawer-plain]')).toBe(true);
      expect(isShown('[data-testid=drawer-markdown]')).toBe(false);
      expect(document.querySelector('[data-testid=drawer-plain]')?.textContent).toBe('+added line\n-removed line\n');
    });
    selectFile(2);
    await eventually(() => {
      expect(isShown('[data-testid=drawer-markdown]')).toBe(true);
      expect(text('[data-testid=drawer-verdict]')).toBe('PASS ok');
      expect(document.querySelector('[data-testid=drawer-verdict]')?.getAttribute('data-tone') === 'good').toBe(true);
      expect(isShown('[data-testid=drawer-summary]')).toBe(true);
      expect(text('[data-testid=drawer-summary]')).toContain('all good');
      expect(text('[data-testid=drawer-body]')).toContain('Details');
    });
  });

  it('hides verdict and summary for a plain markdown file', async () => {
    await openDrawer();
    expect(isShown('[data-testid=drawer-verdict]')).toBe(false);
    expect(isShown('[data-testid=drawer-summary]')).toBe(false);
  });

  it('refreshes with the poll while open and keeps the selected file', async () => {
    await openDrawer();
    selectFile(1);
    await eventually(() => expect(text('[data-testid=drawer-plain]')).toBe('+added line -removed line'));
    taskClient.texts['build.diff'] = '+changed\n';
    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });
    pollAgain();
    await eventually(() => expect(document.querySelector('[data-testid=drawer-plain]')?.textContent).toBe('+changed\n'));
    expect(fileButtons()[1].getAttribute('aria-current')).toBe('true');
  });

  it('refetches the file only when the task or the file entry changed', async () => {
    await openDrawer();
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
    await openDrawer();
    const emphasis = document.querySelector('[data-testid=drawer-body] strong') as HTMLElement;
    emphasis.dataset.kept = 'yes';
    const fetched = taskClient.fileCalls.length;
    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });
    pollAgain();
    await eventually(() => expect(taskClient.fileCalls.length).toBe(fetched + 1));
    await flush();
    expect((document.querySelector('[data-testid=drawer-body] strong') as HTMLElement).dataset.kept).toBe('yes');
    taskClient.texts['spec.md'] = '# Spec\n\nNew **words**';
    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T12:00:00Z' });
    pollAgain();
    await eventually(() => expect(text('[data-testid=drawer-body]')).toContain('New words'));
    expect((document.querySelector('[data-testid=drawer-body] strong') as HTMLElement).dataset.kept).toBeUndefined();
  });

  it('shows nothing, not the previous file, when the newly selected file cannot be loaded', async () => {
    await openDrawer();
    taskClient.failure = new Error('file too large');
    selectFile(1);
    await eventually(() => expect(text('[data-testid=drawer-error]')).toBe('file too large'));
    expect(isShown('[data-testid=drawer-markdown]')).toBe(false);
    expect(document.querySelector('[data-testid=drawer-plain]')?.textContent).toBe('');
    taskClient.failure = null;
    taskClient.detail = sampleDetail({ updatedAt: '2026-11-24T11:00:00Z' });
    pollAgain();
    await eventually(() => expect(document.querySelector('[data-testid=drawer-plain]')?.textContent).toBe('+added line\n-removed line\n'));
    expect(text('[data-testid=drawer-error]')).toBe('');
  });

  it('does not reload while closed', async () => {
    pollAgain();
    await flush();
    expect(taskClient.taskCalls).toBe(0);
  });

  it('falls back to the first file when the selected one disappears', async () => {
    await openDrawer();
    selectFile(1);
    await eventually(() => expect(fileButtons()[1].getAttribute('aria-current')).toBe('true'));
    taskClient.detail = sampleDetail({ files: [sampleDetail().files[0]] });
    pollAgain();
    await eventually(() => {
      expect(fileButtons().map((button) => button.querySelector('span:nth-child(2)')?.textContent)).toEqual(['spec.md']);
      expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');
      expect(isShown('[data-testid=drawer-markdown]')).toBe(true);
    });
  });

  it('shows an empty drawer for a task without files, and no MR link without a URL', async () => {
    taskClient.detail = sampleDetail({ files: [], mrUrl: null, risk: null });
    card().click();
    await eventually(() => {
      expect(text('[data-testid=drawer-headline]')).toBe('demo · fix-export · build · round 1 · 2m · 6.0k tok');
      expect(isShown('[data-testid=drawer-plain]')).toBe(true);
    });
    expect(fileButtons()).toHaveLength(0);
    expect((document.querySelector('.d-head .links') as HTMLElement).style.display).toBe('none');
  });

  it('shows an error when the task cannot be loaded, and keeps content when a refresh fails', async () => {
    taskClient.failure = new Error('task unreadable');
    card().click();
    await eventually(() => expect(text('[data-testid=drawer-error]')).toBe('task unreadable'));
    expect(text('[data-testid=drawer-headline]')).toBe('demo · fix-export');
    press('Escape');
    await eventually(() => expect(isShown('[data-testid=drawer]')).toBe(false));
    taskClient.failure = null;
    await openDrawer();
    expect(text('[data-testid=drawer-error]')).toBe('');
    taskClient.failure = new Error('later failure');
    const callsBefore = taskClient.taskCalls;
    pollAgain();
    expect(taskClient.taskCalls).toBe(callsBefore + 1);
    await flush();
    expect(text('[data-testid=drawer-error]')).toBe('');
    expect(text('[data-testid=drawer-body]')).toContain('Hello');
  });

  it('shows the file error when one file cannot be read', async () => {
    await openDrawer();
    taskClient.failure = new Error('file too large');
    selectFile(1);
    await eventually(() => expect(text('[data-testid=drawer-error]')).toBe('file too large'));
  });

  it('drops an answer that arrives after the drawer was closed', async () => {
    card().click();
    press('Escape');
    await flush();
    expect(isShown('[data-testid=drawer]')).toBe(false);
    expect(text('[data-testid=drawer-headline]')).toBe('demo · fix-export');
  });

  it('drops a failure that arrives after the drawer was closed', async () => {
    taskClient.failure = new Error('late');
    card().click();
    press('Escape');
    await flush();
    expect(text('[data-testid=drawer-error]')).toBe('');
  });

  it('drops a file answer that arrives after the selection moved on', async () => {
    await openDrawer();
    selectFile(1);
    selectFile(0);
    await flush();
    expect(fileButtons()[0].getAttribute('aria-current')).toBe('true');
    expect(isShown('[data-testid=drawer-markdown]')).toBe(true);
  });

  it('drops a file failure that arrives after the drawer was closed', async () => {
    await openDrawer();
    taskClient.failure = new Error('late file');
    selectFile(1);
    press('Escape');
    await flush();
    expect(text('[data-testid=drawer-error]')).toBe('');
  });
});
