import type { BoardAgent, BoardSnapshot, BoardTask } from './types';

export interface ColumnView {
  name: string;
  tasks: BoardTask[];
}

export function projectNames(snapshot: BoardSnapshot): string[] {
  return snapshot.projects.map((project) => project.name);
}

/** One entry per snapshot column, in order, so empty columns stay visible. */
export function groupTasksByColumn(snapshot: BoardSnapshot, project: string | null): ColumnView[] {
  const tasks = snapshot.projects
    .filter((candidate) => project === null || candidate.name === project)
    .flatMap((candidate) => candidate.tasks);
  return snapshot.columns.map((name) => ({ name, tasks: tasks.filter((task) => task.column === name) }));
}

export function agentsWorkingOn(agents: BoardAgent[], task: BoardTask): BoardAgent[] {
  return agents.filter((agent) => agent.project === task.project && agent.slug === task.slug);
}
