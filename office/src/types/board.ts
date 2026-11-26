interface HistoryEntry {
  ts: string;
  stage: string;
  column: string;
  reason: string | null;
}

interface ColumnDuration {
  column: string;
  milliseconds: number;
}

interface TaskMetrics {
  manualAcceptanceCriteria: number;
  needsHumanCount: number;
  needsHumanMilliseconds: number;
}

interface BoardTask {
  project: string;
  slug: string;
  title: string;
  stage: string;
  column: string;
  merged: boolean | null;
  next: string;
  reason: string | null;
  question: string | null;
  history: HistoryEntry[];
  durations: ColumnDuration[];
  metrics: TaskMetrics;
}

interface BoardProject {
  name: string;
  tasks: BoardTask[];
}

/** A `spawn` record of the argani event log. */
interface BoardAgent {
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

interface BoardSnapshot {
  home: string;
  generatedAt: string;
  columns: string[];
  projects: BoardProject[];
  agents: BoardAgent[];
}

export type { HistoryEntry, ColumnDuration, TaskMetrics, BoardTask, BoardProject, BoardAgent, BoardSnapshot };
