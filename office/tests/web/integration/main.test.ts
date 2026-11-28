// @vitest-environment happy-dom
import { expect, it, vi } from 'vitest';
import { sampleSnapshot, sampleTasks } from '../sample-snapshot';
import pageMarkup from './page-markup';
import eventually from './eventually';

it('wires clients, poller, clipboard and dashboard against /api/board and /api/tasks', async () => {
  const fetchSpy = vi.fn(async (url: string) => Response.json(url === '/api/board' ? sampleSnapshot() : { tasks: sampleTasks() }));

  vi.stubGlobal('fetch', fetchSpy);

  const writeText = vi.fn(async (_text: string) => {});

  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });

  document.body.innerHTML = pageMarkup();

  await import('@/main');

  await eventually(() => expect(document.querySelectorAll('.card')).toHaveLength(3));

  (document.querySelector('[data-testid=row-copy]') as HTMLElement).click();

  await eventually(() => expect(writeText).toHaveBeenCalledWith('/argani:factory answer stuck <answer>'));

  expect(fetchSpy).toHaveBeenCalledWith('/api/board', { signal: expect.any(AbortSignal) });

  expect(fetchSpy).toHaveBeenCalledWith('/api/tasks', { signal: expect.any(AbortSignal) });
});
