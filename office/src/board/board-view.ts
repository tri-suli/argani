import { formatCount, formatDuration } from '@/board/format';
import { NO_COUNT } from '@/constants/dashboard';
import { DONE, NEEDS_HUMAN, PIPELINE, PIPELINE_NAMES, WORKING_COLUMNS } from '@/constants/pipeline';
import { CHIP_CLASS_INVALID, CHIP_CLASS_PENDING, CHIP_CLASS_WAITING, REVIEW_STATE_INVALID, REVIEW_STATE_PENDING } from '@/constants/review';
import type { BoardAgent, BoardSnapshot, BoardTask } from '@/types/board';
import type { ReviewState, TaskSummary } from '@/types/task';
import type { BoardTotals, CardView, ColumnView, HistoryRow } from '@/types/view';

class BoardView {
  columnOf(task: BoardTask): string {
    return PIPELINE_NAMES.has(task.column) ? task.column : NEEDS_HUMAN;
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

  /** Manual acceptance criteria and time spent in Needs human over the tasks of the shown project (every project when null). */
  totalsOf(snapshot: BoardSnapshot, project: string | null): BoardTotals {
    const tasks = snapshot.projects.filter((candidate) => project === null || candidate.name === project).flatMap((candidate) => candidate.tasks);

    return {
      manualAcceptanceCriteria: tasks.reduce((sum, task) => sum + task.metrics.manualAcceptanceCriteria, 0),
      needsHumanMilliseconds: tasks.reduce((sum, task) => sum + task.metrics.needsHumanMilliseconds, 0),
    };
  }

  findTask(snapshot: BoardSnapshot | null, project: string, slug: string): BoardTask | null {
    return snapshot?.projects.flatMap((candidate) => candidate.tasks).find((task) => task.project === project && task.slug === slug) ?? null;
  }

  /** The columns the task has been through, in order, each with the time it stayed. */
  historyRows(task: BoardTask): HistoryRow[] {
    return task.durations.map(({ column, milliseconds }) => ({ column, duration: formatDuration(milliseconds) }));
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

    const needsHuman = column === NEEDS_HUMAN;

    const waited = task.metrics.needsHumanCount;

    const rounds = (summary?.rounds ?? []).map((round) => ({
      n: round.n,
      label: `R${round.n}`,
      chips: Object.entries(round.reviews).map(([reviewer, state]) => ({ reviewer, state, className: this.chipClassName(state, inProgress) })),
    }));

    return {
      key: `${task.project}/${task.slug}`,
      task,
      active: this.agentsWorkingOn(agents, task).length > NO_COUNT,
      risk: summary?.risk ?? null,
      rounds,
      mrUrl: summary?.mrUrl ?? null,
      time: summary && summary.agentMilliseconds > NO_COUNT ? formatDuration(summary.agentMilliseconds) : '',
      tokens: summary && summary.tokens.total > NO_COUNT ? `${formatCount(summary.tokens.total)} tok` : '',
      flag: needsHuman ? (task.reason ?? NEEDS_HUMAN) : null,
      hasBadge: waited > NO_COUNT,
      badge: waited > NO_COUNT ? `${waited}× you` : '',
      hint: needsHuman ? task.question : null,
      dimmed: column === DONE,
    };
  }
}

export default BoardView;
