import { formatCount, formatDuration } from './format';
import type { BoardAgent, BoardSnapshot, BoardTask, ReviewState, Risk, TaskSummary } from './types';

export interface PipelineColumn {
  name: string;
  who: string;
  tone: '' | 'human' | 'merged';
}

/** The factory pipeline, fixed and independent of the plugin's own columns. */
export const PIPELINE: PipelineColumn[] = [
  { name: 'Intake', who: 'intent · you approve', tone: '' },
  { name: 'Spec', who: 'spec-writer', tone: '' },
  { name: 'Build', who: 'builder · verify', tone: '' },
  { name: 'Review', who: 'reviewers', tone: '' },
  { name: 'Approve', who: 'approver · you merge', tone: '' },
  { name: 'Needs human', who: 'you', tone: 'human' },
  { name: 'Done', who: 'merged', tone: 'merged' },
];

// Stage names come from plugins/argani/scripts/factory_state.py decide_stage; an unknown one lands in Needs human.
const STAGE_COLUMN: Record<string, string> = {
  'needs-intent-approval': 'Intake',
  'needs-spec': 'Spec',
  'needs-spec-approval': 'Spec',
  'needs-build': 'Build',
  'needs-rework': 'Build',
  'needs-review': 'Review',
  'needs-decision': 'Approve',
  'needs-mr': 'Approve',
};

/** Stages whose next step is the human's, besides every card in Needs human. */
const HUMAN_STAGES = new Set(['needs-intent-approval', 'needs-spec-approval']);

const NEEDS_HUMAN = 'Needs human';
const DONE = 'Done';
const WORKING_COLUMNS = new Set(['Build', 'Review']);

export function columnOf(task: BoardTask): string {
  if (task.stage === 'done') {
    return task.merged === true ? DONE : 'Approve';
  }
  return STAGE_COLUMN[task.stage] ?? NEEDS_HUMAN;
}

function waitsForHuman(task: BoardTask, column: string): boolean {
  return column === NEEDS_HUMAN || HUMAN_STAGES.has(task.stage) || (task.stage === 'done' && column !== DONE);
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
