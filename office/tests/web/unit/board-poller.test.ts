import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BoardPoller } from '../../../src/board/board-poller';
import type { BoardClient } from '../../../src/board/board-client';
import { sampleSnapshot } from '../sample-snapshot';

describe('BoardPoller', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const handlersSpy = () => ({ onSnapshot: vi.fn(), onError: vi.fn() });

  it('polls immediately and then every interval, until stopped', async () => {
    const client: BoardClient = { fetchBoard: vi.fn(async () => sampleSnapshot()) };
    const handlers = handlersSpy();
    const poller = new BoardPoller(client, 1000);
    poller.start(handlers);
    await vi.advanceTimersByTimeAsync(2500);
    expect(handlers.onSnapshot).toHaveBeenCalledTimes(3);
    poller.stop();
    poller.stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(handlers.onSnapshot).toHaveBeenCalledTimes(3);
  });

  it('uses 5000 ms by default', async () => {
    const client: BoardClient = { fetchBoard: vi.fn(async () => sampleSnapshot()) };
    const poller = new BoardPoller(client);
    poller.start(handlersSpy());
    await vi.advanceTimersByTimeAsync(4999);
    expect(client.fetchBoard).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(client.fetchBoard).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it('reports errors, wraps non-errors, and recovers on the next success', async () => {
    const fetchBoard = vi
      .fn<BoardClient['fetchBoard']>()
      .mockRejectedValueOnce(new Error('down'))
      .mockRejectedValueOnce('plain string')
      .mockResolvedValue(sampleSnapshot());
    const handlers = handlersSpy();
    const poller = new BoardPoller({ fetchBoard }, 1000);
    poller.start(handlers);
    await vi.advanceTimersByTimeAsync(2000);
    expect(handlers.onError.mock.calls.map(([error]) => error.message)).toEqual(['down', 'plain string']);
    expect(handlers.onSnapshot).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it('never overlaps requests', async () => {
    const fetchBoard = vi.fn(() => new Promise<never>(() => {}));
    const poller = new BoardPoller({ fetchBoard }, 1000);
    poller.start(handlersSpy());
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchBoard).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it('restarting replaces the previous timer', async () => {
    const client: BoardClient = { fetchBoard: vi.fn(async () => sampleSnapshot()) };
    const poller = new BoardPoller(client, 1000);
    poller.start(handlersSpy());
    poller.start(handlersSpy());
    await vi.advanceTimersByTimeAsync(1000);
    expect(client.fetchBoard).toHaveBeenCalledTimes(2);
    poller.stop();
  });
});
