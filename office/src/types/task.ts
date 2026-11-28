type Risk = 'low' | 'medium' | 'high';

type ReviewState = 'PASS' | 'CHANGES' | 'pending' | 'invalid';

/** A review round that is decided: every reviewer passed, or one asked for changes. */
type ReviewOutcome = 'PASS' | 'CHANGES';

type FileTone = 'good' | 'warn' | 'stop';

interface TaskRound {
  n: number;
  reviews: Record<string, ReviewState>;
}

interface TokenUsage {
  input: number;
  output: number;
  cacheCreation: number;
  cacheRead: number;
  total: number;
}

/** One entry of `GET /api/tasks`. */
interface TaskSummary {
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

interface TaskFile {
  path: string;
  group: string;
  firstLine: string;
  tone: FileTone | null;
}

/** `GET /api/tasks/<project>/<slug>`. */
interface TaskDetail extends TaskSummary {
  next: string;
  column: string;
  reviewers: string[];
  models: Record<string, unknown> | null;
  decision: { exists: boolean; complete: boolean; verdict: string | null } | null;
  files: TaskFile[];
}

export type { Risk, ReviewState, ReviewOutcome, FileTone, TaskRound, TokenUsage, TaskSummary, TaskFile, TaskDetail };
