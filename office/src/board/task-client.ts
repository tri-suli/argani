import { DEFAULT_TIMEOUT_MILLISECONDS } from './constants';
import requestOk from './http';
import type { FetchFunction, TaskClient, TaskDetail, TaskSummary } from './types';

class FetchTaskClient implements TaskClient {
  constructor(
    private readonly fetchFunction: FetchFunction,
    private readonly baseUrl: string,
    private readonly timeoutMilliseconds: number = DEFAULT_TIMEOUT_MILLISECONDS,
  ) {}

  async fetchTasks(): Promise<TaskSummary[]> {
    return ((await (await this.get(this.baseUrl)).json()) as { tasks: TaskSummary[] }).tasks;
  }

  async fetchTask(project: string, slug: string): Promise<TaskDetail> {
    return (await (await this.get(this.taskUrl(project, slug))).json()) as TaskDetail;
  }

  async fetchFile(project: string, slug: string, path: string): Promise<string> {
    return (await this.get(`${this.taskUrl(project, slug)}/file?path=${encodeURIComponent(path)}`)).text();
  }

  private taskUrl(project: string, slug: string): string {
    return `${this.baseUrl}/${encodeURIComponent(project)}/${encodeURIComponent(slug)}`;
  }

  private get(url: string): Promise<Response> {
    return requestOk(this.fetchFunction, url, this.timeoutMilliseconds);
  }
}

export default FetchTaskClient;
