import { DEFAULT_TIMEOUT_MILLISECONDS, requestOk, type FetchFunction } from './http';
import type { BoardSnapshot } from './types';

export interface BoardClient {
  fetchBoard(): Promise<BoardSnapshot>;
}

export class FetchBoardClient implements BoardClient {
  constructor(
    private readonly fetchFunction: FetchFunction,
    private readonly url: string,
    private readonly timeoutMilliseconds: number = DEFAULT_TIMEOUT_MILLISECONDS,
  ) {}

  async fetchBoard(): Promise<BoardSnapshot> {
    const response = await requestOk(this.fetchFunction, this.url, this.timeoutMilliseconds);
    return (await response.json()) as BoardSnapshot;
  }
}
