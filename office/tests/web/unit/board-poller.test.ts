import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BoardPoller from '../../../src/board/board-poller';
import type { BoardClient } from '../../../src/board/types';
import { sampleSnapshot, sampleTasks } from '../sample-snapshot';

const taskClient = { fetchTasks: vi.fn(async () => sampleTasks()) };

describe('BoardPoller', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const handlersSpy = () => ({ onSnapshot: vi.fn(), onError: vi.fn() });

  it('polls immediately and then every interval, until stopped', async () => {
    const client: BoardClient = { fetchBoard: vi.fn(async () => sampleSnapshot()) };
    const handlers = handlersSpy();
    const poller = new BoardPoller(client, taskClient, 1000);
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
    const poller = new BoardPoller(client, taskClient);
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
    const poller = new BoardPoller({ fetchBoard }, taskClient, 1000);
    poller.start(handlers);
    await vi.advanceTimersByTimeAsync(2000);
    expect(handlers.onError.mock.calls.map(([error]) => error.message)).toEqual(['down', 'plain string']);
    expect(handlers.onSnapshot).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it('delivers the board and the tasks together', async () => {
    const handlers = handlersSpy();
    const poller = new BoardPoller({ fetchBoard: async () => sampleSnapshot() }, taskClient, 1000);
    poller.start(handlers);
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.onSnapshot).toHaveBeenCalledWith(sampleSnapshot(), sampleTasks());
    poller.stop();
  });

  it('fails the whole cycle when only the task request fails', async () => {
    const handlers = handlersSpy();
    const failingTasks = { fetchTasks: vi.fn(async () => Promise.reject(new Error('tasks down'))) };
    const poller = new BoardPoller({ fetchBoard: async () => sampleSnapshot() }, failingTasks, 1000);
    poller.start(handlers);
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.onSnapshot).not.toHaveBeenCalled();
    expect(handlers.onError.mock.calls[0][0].message).toBe('tasks down');
    poller.stop();
  });

  it('never overlaps requests', async () => {
    const fetchBoard = vi.fn(() => new Promise<never>(() => {}));
    const poller = new BoardPoller({ fetchBoard }, taskClient, 1000);
    poller.start(handlersSpy());
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchBoard).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it('restarting replaces the previous timer', async () => {
    const client: BoardClient = { fetchBoard: vi.fn(async () => sampleSnapshot()) };
    const poller = new BoardPoller(client, taskClient, 1000);
    poller.start(handlersSpy());
    poller.start(handlersSpy());
    await vi.advanceTimersByTimeAsync(1000);
    expect(client.fetchBoard).toHaveBeenCalledTimes(2);
    poller.stop();
  });
});
