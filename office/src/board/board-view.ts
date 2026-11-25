import { formatCount, formatDuration } from '@/board/format';
import {
  CHIP_CLASS_INVALID,
  CHIP_CLASS_PENDING,
  CHIP_CLASS_WAITING,
  COLUMN_APPROVE,
  DONE,
  HUMAN_STAGES,
  NEEDS_HUMAN,
  PIPELINE,
  REVIEW_STATE_INVALID,
  REVIEW_STATE_PENDING,
  STAGE_COLUMN,
  STAGE_DONE,
  WORKING_COLUMNS,
} from '@/board/constants';
import type { BoardAgent, BoardSnapshot, BoardTask, CardView, ColumnView, ReviewState, TaskSummary } from '@/board/types';

class BoardView {
  columnOf(task: BoardTask): string {
    if (task.stage === STAGE_DONE) {
      return task.merged === true ? DONE : COLUMN_APPROVE;
    }
    return STAGE_COLUMN[task.stage] ?? NEEDS_HUMAN;
  }

  projectNames(snapshot: BoardSnapshot): string[] {
    return snapshot.projects.map((project) => project.name);
  }

  agentsWorkingOn(agents: BoardAgent[], task: BoardTask): BoardAgent[] {
    return agents.filter((agent) => agent.project === task.project && agent.slug === task.slug);
  }

  chipClassName(state: ReviewState, taskInProgress: boolean): string {
    if (state === REVIEW_STATE_PENDING) {
      return taskInProgress ? CHIP_CLASS_WAITING : CHIP_CLASS_PENDING;
    }
    return state === REVIEW_STATE_INVALID ? CHIP_CLASS_INVALID : state;
  }

  /** One entry per pipeline column, in order, so empty columns stay visible. */
  groupTasksByColumn(snapshot: BoardSnapshot, tasks: TaskSummary[], project: string | null): ColumnView[] {
    const summaries = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary]));
    const updatedAt = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary.updatedAt]));
    const cards = snapshot.projects
      .filter((candidate) => project === null || candidate.name === project)
      .flatMap((candidate) => candidate.tasks)
      .map((task) => this.buildCard(task, summaries.get(`${task.project}/${task.slug}`), snapshot.agents));
    return PIPELINE.map(({ name, who, tone }) => ({
      name,
      who,
      tone,
      cards: cards.filter((card) => this.columnOf(card.task) === name).sort((left, right) => this.byNewest(left, right, updatedAt)),
    }));
  }

  totalTokens(tasks: TaskSummary[]): number {
    return tasks.reduce((sum, summary) => sum + summary.tokens.total, 0);
  }

  private waitsForHuman(task: BoardTask, column: string): boolean {
    return column === NEEDS_HUMAN || HUMAN_STAGES.has(task.stage) || (task.stage === STAGE_DONE && column !== DONE);
  }

  /** Newest first; tasks without a timestamp go last, ties keep a stable slug order. */
  private byNewest(left: CardView, right: CardView, updatedAt: Map<string, string | null>): number {
    const leftTime = updatedAt.get(left.key) ?? '';
    const rightTime = updatedAt.get(right.key) ?? '';
    return rightTime.localeCompare(leftTime) || left.key.localeCompare(right.key);
  }

  private buildCard(task: BoardTask, summary: TaskSummary | undefined, agents: BoardAgent[]): CardView {
    const column = this.columnOf(task);
    const inProgress = WORKING_COLUMNS.has(column);
    const needsHuman = this.waitsForHuman(task, column);
    const rounds = (summary?.rounds ?? []).map((round) => ({
      n: round.n,
      label: `R${round.n}`,
      chips: Object.entries(round.reviews).map(([reviewer, state]) => ({ reviewer, state, className: this.chipClassName(state, inProgress) })),
    }));
    return {
      key: `${task.project}/${task.slug}`,
      task,
      active: this.agentsWorkingOn(agents, task).length > 0,
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
}

export default BoardView;
