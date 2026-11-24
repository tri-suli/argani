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
