import { describe, expect, it, vi } from 'vitest';
import { FetchBoardClient } from '../../../src/board/board-client';
import { FetchTaskClient } from '../../../src/board/task-client';
import { sampleDetail, sampleSnapshot, sampleTasks } from '../sample-snapshot';

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

describe('FetchTaskClient', () => {
  it('unwraps the task list', async () => {
    const fetchFunction = vi.fn(async () => Response.json({ tasks: sampleTasks() }));
    expect(await new FetchTaskClient(fetchFunction, '/api/tasks').fetchTasks()).toEqual(sampleTasks());
    expect(fetchFunction).toHaveBeenCalledWith('/api/tasks', { signal: expect.any(AbortSignal) });
  });

  it('encodes project and slug when fetching one task', async () => {
    const fetchFunction = vi.fn(async (_url: string) => Response.json(sampleDetail()));
    expect(await new FetchTaskClient(fetchFunction, '/api/tasks').fetchTask('my project', 'a/b')).toEqual(sampleDetail());
    expect(fetchFunction.mock.calls[0][0]).toBe('/api/tasks/my%20project/a%2Fb');
  });

  it('fetches a file as text with the path encoded', async () => {
    const fetchFunction = vi.fn(async (_url: string) => new Response('file text'));
    expect(await new FetchTaskClient(fetchFunction, '/api/tasks').fetchFile('demo', 'ship', 'review/round-1/x.md')).toBe('file text');
    expect(fetchFunction.mock.calls[0][0]).toBe('/api/tasks/demo/ship/file?path=review%2Fround-1%2Fx.md');
  });

  it('throws the backend error message', async () => {
    const client = new FetchTaskClient(vi.fn(async () => Response.json({ error: 'file too large' }, { status: 413 })), '/api/tasks');
    await expect(client.fetchFile('demo', 'ship', 'big.diff')).rejects.toThrow('file too large');
  });
});
