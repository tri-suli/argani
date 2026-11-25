import type { FetchFunction } from './types';

/** Resolves with an ok response; otherwise throws the backend's `{error}` message or the HTTP status. */
async function requestOk(fetchFunction: FetchFunction, url: string, timeoutMilliseconds: number): Promise<Response> {
  const response = await fetchFunction(url, { signal: AbortSignal.timeout(timeoutMilliseconds) });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return response;
}

async function describeFailure(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: unknown };
    if (typeof body.error === 'string') {
      return body.error;
    }
  } catch {
    // body is not JSON: fall back to the status
  }
  return `HTTP ${response.status}`;
}

export default requestOk;
