import type { BoardSnapshot } from '@/types/board';
import type { TaskDetail, TaskSummary } from '@/types/task';

interface BoardClient {
  fetchBoard(): Promise<BoardSnapshot>;
}

interface TaskClient {
  fetchTasks(): Promise<TaskSummary[]>;
  fetchTask(project: string, slug: string): Promise<TaskDetail>;
  fetchFile(project: string, slug: string, path: string): Promise<string>;
}

type FetchFunction = (url: string, init: RequestInit) => Promise<Response>;

export type { BoardClient, TaskClient, FetchFunction };
