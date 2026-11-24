import { formatCount, formatDuration } from './format';
import type { BoardAgent, BoardSnapshot, BoardTask, ReviewState, Risk, TaskSummary } from './types';

/** Who works on a column, shown under its name. */
export const COLUMN_WHO: Record<string, string> = {
  Backlog: 'intent · you approve',
  Design: 'spec-writer',
  'In progress': 'builder · reviewers',
  'Ready for MR': 'approver',
  'In review': 'you · merge request',
  Done: 'merged',
  'Needs human': 'you',
};

const NEEDS_HUMAN = 'Needs human';
const IN_PROGRESS = 'In progress';
const DONE = 'Done';

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
  const inProgress = task.column === IN_PROGRESS;
  const needsHuman = task.column === NEEDS_HUMAN;
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
    dimmed: task.column === DONE,
  };
}

/** One entry per snapshot column, in order, so empty columns stay visible. */
export function groupTasksByColumn(snapshot: BoardSnapshot, tasks: TaskSummary[], project: string | null): ColumnView[] {
  const summaries = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary]));
  const updatedAt = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary.updatedAt]));
  const cards = snapshot.projects
    .filter((candidate) => project === null || candidate.name === project)
    .flatMap((candidate) => candidate.tasks)
    .map((task) => buildCard(task, summaries.get(`${task.project}/${task.slug}`), snapshot.agents));
  return snapshot.columns.map((name) => ({
    name,
    who: COLUMN_WHO[name] ?? '',
    tone: name === NEEDS_HUMAN ? 'human' : name === DONE ? 'merged' : '',
    cards: cards.filter((card) => card.task.column === name).sort((left, right) => byNewest(left, right, updatedAt)),
  }));
}

export function totalTokens(tasks: TaskSummary[]): number {
  return tasks.reduce((sum, summary) => sum + summary.tokens.total, 0);
}
