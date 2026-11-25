import { formatCount, formatDuration } from './format';
import { DONE, HUMAN_STAGES, NEEDS_HUMAN, PIPELINE, STAGE_COLUMN, WORKING_COLUMNS } from './constants';
import type { BoardAgent, BoardSnapshot, BoardTask, CardView, ColumnView, ReviewState, TaskSummary } from './types';

export function columnOf(task: BoardTask): string {
  if (task.stage === 'done') {
    return task.merged === true ? DONE : 'Approve';
  }
  return STAGE_COLUMN[task.stage] ?? NEEDS_HUMAN;
}

function waitsForHuman(task: BoardTask, column: string): boolean {
  return column === NEEDS_HUMAN || HUMAN_STAGES.has(task.stage) || (task.stage === 'done' && column !== DONE);
}

export function projectNames(snapshot: BoardSnapshot): string[] {
  return snapshot.projects.map((project) => project.name);
}

export function agentsWorkingOn(agents: BoardAgent[], task: BoardTask): BoardAgent[] {
  return agents.filter((agent) => agent.project === task.project && agent.slug === task.slug);
}

export function chipClassName(state: ReviewState, taskInProgress: boolean): string {
  if (state === 'pending') {
    return taskInProgress ? 'wait' : 'pending';
  }
  return state === 'invalid' ? 'bad' : state;
}

/** Newest first; tasks without a timestamp go last, ties keep a stable slug order. */
function byNewest(left: CardView, right: CardView, updatedAt: Map<string, string | null>): number {
  const leftTime = updatedAt.get(left.key) ?? '';
  const rightTime = updatedAt.get(right.key) ?? '';
  return rightTime.localeCompare(leftTime) || left.key.localeCompare(right.key);
}

function buildCard(task: BoardTask, summary: TaskSummary | undefined, agents: BoardAgent[]): CardView {
  const column = columnOf(task);
  const inProgress = WORKING_COLUMNS.has(column);
  const needsHuman = waitsForHuman(task, column);
  const rounds = (summary?.rounds ?? []).map((round) => ({
    n: round.n,
    label: `R${round.n}`,
    chips: Object.entries(round.reviews).map(([reviewer, state]) => ({ reviewer, state, className: chipClassName(state, inProgress) })),
  }));
  return {
    key: `${task.project}/${task.slug}`,
    task,
    active: agentsWorkingOn(agents, task).length > 0,
    risk: summary?.risk ?? null,
    rounds,
    mrUrl: summary?.mrUrl ?? null,
    time: summary && summary.agentMilliseconds > 0 ? formatDuration(summary.agentMilliseconds) : '',
    tokens: summary && summary.tokens.total > 0 ? `${formatCount(summary.tokens.total)} tok` : '',
    flag: needsHuman ? 'your call' : null,
    hint: needsHuman ? task.next : null,
    dimmed: column === DONE,
  };
}

/** One entry per pipeline column, in order, so empty columns stay visible. */
export function groupTasksByColumn(snapshot: BoardSnapshot, tasks: TaskSummary[], project: string | null): ColumnView[] {
  const summaries = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary]));
  const updatedAt = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary.updatedAt]));
  const cards = snapshot.projects
    .filter((candidate) => project === null || candidate.name === project)
    .flatMap((candidate) => candidate.tasks)
    .map((task) => buildCard(task, summaries.get(`${task.project}/${task.slug}`), snapshot.agents));
  return PIPELINE.map(({ name, who, tone }) => ({
    name,
    who,
    tone,
    cards: cards.filter((card) => columnOf(card.task) === name).sort((left, right) => byNewest(left, right, updatedAt)),
  }));
}

export function totalTokens(tasks: TaskSummary[]): number {
  return tasks.reduce((sum, summary) => sum + summary.tokens.total, 0);
}
