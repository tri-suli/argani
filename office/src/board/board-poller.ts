import type { BoardClient } from './board-client';
import type { BoardSnapshot } from './types';

export interface PollHandlers {
  onSnapshot(snapshot: BoardSnapshot): void;
  onError(error: Error): void;
}

export interface Poller {
  start(handlers: PollHandlers): void;
  stop(): void;
}

export class BoardPoller implements Poller {
  private timer: ReturnType<typeof setInterval> | null = null;
  private requestInFlight = false;

  constructor(
    private readonly client: BoardClient,
    private readonly intervalMilliseconds = 5000,
  ) {}

  start(handlers: PollHandlers): void {
    this.stop();
    void this.poll(handlers);
    this.timer = setInterval(() => void this.poll(handlers), this.intervalMilliseconds);
  }

  stop(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private async poll(handlers: PollHandlers): Promise<void> {
    if (this.requestInFlight) {
      return;
    }
    this.requestInFlight = true;
    try {
      handlers.onSnapshot(await this.client.fetchBoard());
    } catch (error) {
      handlers.onError(error instanceof Error ? error : new Error(String(error)));
    } finally {
      this.requestInFlight = false;
    }
  }
}
