import type { BoardSnapshot } from './types';

export interface BoardClient {
  fetchBoard(): Promise<BoardSnapshot>;
}

export type FetchFunction = (url: string, init: RequestInit) => Promise<Response>;

// Shorter than the poll interval: a backend that never answers must surface as a failure, not a hang.
export const DEFAULT_TIMEOUT_MILLISECONDS = 4000;

export class FetchBoardClient implements BoardClient {
  constructor(
    private readonly fetchFunction: FetchFunction,
    private readonly url: string,
    private readonly timeoutMilliseconds: number = DEFAULT_TIMEOUT_MILLISECONDS,
  ) {}

  async fetchBoard(): Promise<BoardSnapshot> {
    const response = await this.fetchFunction(this.url, { signal: AbortSignal.timeout(this.timeoutMilliseconds) });
    if (!response.ok) {
      throw new Error(await this.describeFailure(response));
    }
    return (await response.json()) as BoardSnapshot;
  }

  private async describeFailure(response: Response): Promise<string> {
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
}
