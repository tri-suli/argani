// @vitest-environment happy-dom
import { expect, it, vi } from 'vitest';
import { sampleSnapshot } from '../sample-snapshot';
import { pageMarkup } from './page-markup';

it('wires client, poller and dashboard against /api/board', async () => {
  const fetchSpy = vi.fn(async () => Response.json(sampleSnapshot()));
  vi.stubGlobal('fetch', fetchSpy);
  document.body.innerHTML = pageMarkup();
  await import('../../../src/main');
  await vi.waitFor(() => expect(document.querySelectorAll('.card')).toHaveLength(3));
  expect(fetchSpy).toHaveBeenCalledWith('/api/board', { signal: expect.any(AbortSignal) });
});
