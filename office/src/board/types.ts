export interface BoardTask {
  project: string;
  slug: string;
  title: string;
  stage: string;
  column: string;
  merged: boolean | null;
  next: string;
}

export interface BoardProject {
  name: string;
  tasks: BoardTask[];
}

/** A `spawn` record of the argani event log. */
export interface BoardAgent {
  ts: string;
  event: string;
  session_id: string;
  agent_type: string;
  tool_use_id: string;
  model?: string;
  project: string;
  slug: string | null;
  parent_agent_type: string | null;
  cwd: string;
}

export interface BoardSnapshot {
  home: string;
  generatedAt: string;
  columns: string[];
  projects: BoardProject[];
  agents: BoardAgent[];
}

export type Risk = 'low' | 'medium' | 'high';
export type ReviewState = 'PASS' | 'CHANGES' | 'pending' | 'invalid';
export type FileTone = 'good' | 'warn' | 'stop';

export interface TaskRound {
  n: number;
  reviews: Record<string, ReviewState>;
}

export interface TokenUsage {
  input: number;
  output: number;
  cacheCreation: number;
  cacheRead: number;
  total: number;
}

/** One entry of `GET /api/tasks`. */
export interface TaskSummary {
  project: string;
  slug: string;
  stage: string;
  risk: Risk | null;
  round: number;
  rounds: TaskRound[];
  mrUrl: string | null;
  updatedAt: string | null;
  agentMilliseconds: number;
  tokens: TokenUsage;
}

export interface TaskFile {
  path: string;
  group: string;
  firstLine: string;
  tone: FileTone | null;
}

/** `GET /api/tasks/<project>/<slug>`. */
export interface TaskDetail extends TaskSummary {
  next: string;
  column: string;
  reviewers: string[];
  models: Record<string, unknown> | null;
  decision: { exists: boolean; complete: boolean; verdict: string | null } | null;
  files: TaskFile[];
}

export interface BoardClient {
  fetchBoard(): Promise<BoardSnapshot>;
}

export interface TaskClient {
  fetchTasks(): Promise<TaskSummary[]>;
  fetchTask(project: string, slug: string): Promise<TaskDetail>;
  fetchFile(project: string, slug: string, path: string): Promise<string>;
}

export interface PollHandlers {
  onSnapshot(snapshot: BoardSnapshot, tasks: TaskSummary[]): void;
  onError(error: Error): void;
}

export interface Poller {
  start(handlers: PollHandlers): void;
  stop(): void;
}

export type FetchFunction = (url: string, init: RequestInit) => Promise<Response>;

export interface FileGroup {
  name: string;
  files: TaskFile[];
}

export interface RenderedDocument {
  /** First line of the file, shown as a badge, when the file has a tone. */
  verdict: string | null;
  tone: FileTone | null;
  /** The `## Summary` section, if any. */
  summaryHtml: string | null;
  bodyHtml: string;
}

export interface PipelineColumn {
  name: string;
  who: string;
  tone: '' | 'human' | 'merged';
}

export interface ChipView {
  reviewer: string;
  state: ReviewState;
  className: string;
}

export interface RoundView {
  n: number;
  label: string;
  chips: ChipView[];
}

export interface CardView {
  key: string;
  task: BoardTask;
  active: boolean;
  risk: Risk | null;
  rounds: RoundView[];
  mrUrl: string | null;
  time: string;
  tokens: string;
  flag: string | null;
  hint: string | null;
  dimmed: boolean;
}

export interface ColumnView {
  name: string;
  who: string;
  tone: '' | 'human' | 'merged';
  cards: CardView[];
}
