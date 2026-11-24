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
