export type FetchFunction = (url: string, init: RequestInit) => Promise<Response>;

// Shorter than the poll interval: a backend that never answers must surface as a failure, not a hang.
export const DEFAULT_TIMEOUT_MILLISECONDS = 4000;

/** Resolves with an ok response; otherwise throws the backend's `{error}` message or the HTTP status. */
export async function requestOk(fetchFunction: FetchFunction, url: string, timeoutMilliseconds: number): Promise<Response> {
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
