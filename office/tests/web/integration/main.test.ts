// @vitest-environment happy-dom
import { expect, it, vi } from 'vitest';
import { sampleSnapshot, sampleTasks } from '../sample-snapshot';
import pageMarkup from './page-markup';

it('wires clients, poller and dashboard against /api/board and /api/tasks', async () => {
  const fetchSpy = vi.fn(async (url: string) => Response.json(url === '/api/board' ? sampleSnapshot() : { tasks: sampleTasks() }));

  vi.stubGlobal('fetch', fetchSpy);

  document.body.innerHTML = pageMarkup();

  await import('@/main');

  await vi.waitFor(() => expect(document.querySelectorAll('.card')).toHaveLength(5));

  expect(fetchSpy).toHaveBeenCalledWith('/api/board', { signal: expect.any(AbortSignal) });

  expect(fetchSpy).toHaveBeenCalledWith('/api/tasks', { signal: expect.any(AbortSignal) });
});
