import { DEFAULT_TIMEOUT_MILLISECONDS } from '@/board/constants';
import requestOk from '@/board/http';
import type { BoardClient, BoardSnapshot, FetchFunction } from '@/board/types';

class FetchBoardClient implements BoardClient {
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

export default FetchBoardClient;
