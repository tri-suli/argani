import { DEFAULT_POLL_INTERVAL_MILLISECONDS } from '@/board/constants';
import type { BoardClient, Poller, PollHandlers, TaskClient } from '@/board/types';

class BoardPoller implements Poller {
  private timer: ReturnType<typeof setInterval> | null = null;

  private requestInFlight = false;

  constructor(
    private readonly boardClient: BoardClient,
    private readonly taskClient: Pick<TaskClient, 'fetchTasks'>,
    private readonly intervalMilliseconds = DEFAULT_POLL_INTERVAL_MILLISECONDS,
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
      // Both succeed or the whole cycle fails, so the page never mixes a new board with old task data.
      const [snapshot, tasks] = await Promise.all([this.boardClient.fetchBoard(), this.taskClient.fetchTasks()]);

      handlers.onSnapshot(snapshot, tasks);
    } catch (error) {
      handlers.onError(error instanceof Error ? error : new Error(String(error)));
    } finally {
      this.requestInFlight = false;
    }
  }
}

export default BoardPoller;
