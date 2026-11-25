import type { BoardSnapshot } from '@/types/board';
import type { TaskSummary } from '@/types/task';

interface PollHandlers {
  onSnapshot(snapshot: BoardSnapshot, tasks: TaskSummary[]): void;
  onError(error: Error): void;
}

interface Poller {
  start(handlers: PollHandlers): void;
  stop(): void;
}

export type { PollHandlers, Poller };
