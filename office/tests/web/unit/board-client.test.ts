import { describe, expect, it, vi } from 'vitest';
import { FetchBoardClient } from '../../../src/board/board-client';
import { sampleSnapshot } from '../sample-snapshot';

const clientReturning = (response: Response) => new FetchBoardClient(vi.fn(async () => response), '/api/board');

describe('FetchBoardClient', () => {
  it('requests the url and returns the snapshot', async () => {
    const fetchFunction = vi.fn(async () => Response.json(sampleSnapshot()));
    const client = new FetchBoardClient(fetchFunction, '/api/board');
    expect(await client.fetchBoard()).toEqual(sampleSnapshot());
    expect(fetchFunction).toHaveBeenCalledWith('/api/board', { signal: expect.any(AbortSignal) });
  });

  it('aborts a request that outlives the timeout', async () => {
    const neverAnswering = (_url: string, init: RequestInit) =>
      new Promise<Response>((_resolve, reject) => init.signal?.addEventListener('abort', () => reject(init.signal?.reason)));
    await expect(new FetchBoardClient(neverAnswering, '/api/board', 10).fetchBoard()).rejects.toThrow();
  });

  it('throws the error message of a failed JSON response', async () => {
    await expect(clientReturning(Response.json({ error: 'home missing' }, { status: 500 })).fetchBoard()).rejects.toThrow('home missing');
  });

  it('falls back to the status when the error is not a string', async () => {
    await expect(clientReturning(Response.json({ error: 5 }, { status: 502 })).fetchBoard()).rejects.toThrow('HTTP 502');
  });

  it('falls back to the status when the body is not JSON', async () => {
    await expect(clientReturning(new Response('oops', { status: 503 })).fetchBoard()).rejects.toThrow('HTTP 503');
  });
});
