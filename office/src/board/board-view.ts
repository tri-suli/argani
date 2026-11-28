import { formatCount, formatDuration, formatElapsed, pluralize } from '@/board/format';
import { AGENT_TYPE_SEPARATOR, ALL_PROJECTS, ALL_PROJECTS_LABEL, DETAIL_SEPARATOR, NO_COUNT, NO_VALUE, REASON_WORD_SEPARATOR, TILE_AGENTS, TILE_MANUAL, TILE_TOKENS, NOT_FOUND, TILE_WAITING, UNKNOWN_WAIT } from '@/constants/dashboard';
import { ANSWER_COMMAND_PREFIX, ANSWER_PLACEHOLDER, DONE, KNOWN_COLUMNS, NEEDS_HUMAN, OUTCOME_CANCELLED, OUTCOME_ICONS, OUTCOME_MERGED, PIPELINE, STAGE_CANCELLED, WORKING_COLUMNS } from '@/constants/pipeline';
import { CHIP_CLASS_INVALID, CHIP_CLASS_PENDING, CHIP_CLASS_WAITING, CHIP_ICONS, REVIEW_STATE_INVALID, REVIEW_STATE_PENDING, RISK_ICONS } from '@/constants/review';
import type { BoardAgent, BoardSnapshot, BoardTask } from '@/types/board';
import type { ReviewState, TaskSummary } from '@/types/task';
import type { AgentView, CardView, ColumnView, DoneRow, HistoryRow, NeedsHumanRow, ProjectOption, TotalsTile } from '@/types/view';

class BoardView {
  columnOf(task: BoardTask): string {
    return KNOWN_COLUMNS.has(task.column) ? task.column : NEEDS_HUMAN;
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

  /** One entry per pipeline column, in order, so empty columns stay visible; Needs human and Done tasks have their own lists. */
  groupTasksByColumn(snapshot: BoardSnapshot, tasks: TaskSummary[], project: string | null, nowMilliseconds: number): ColumnView[] {
    const summaries = this.summariesByKey(tasks);

    const updatedAt = new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary.updatedAt]));

    const cards = this.tasksOf(snapshot, project).map((task) => this.buildCard(task, summaries.get(`${task.project}/${task.slug}`), snapshot.agents, nowMilliseconds));

    return PIPELINE.map(({ step, name, who }) => ({
      step,
      name,
      who,
      cards: cards.filter((card) => this.columnOf(card.task) === name).sort((left, right) => this.byNewest(left, right, updatedAt)),
    }));
  }

  /** The tasks waiting for a human answer, the one waiting longest first; tasks whose wait cannot be measured go last. */
  needsHumanRows(snapshot: BoardSnapshot, project: string | null, nowMilliseconds: number): NeedsHumanRow[] {
    return this.tasksOf(snapshot, project)
      .filter((task) => this.columnOf(task) === NEEDS_HUMAN)
      .map((task) => ({ task, waited: this.waitedMilliseconds(task, nowMilliseconds) }))
      .sort((left, right) => (right.waited ?? UNKNOWN_WAIT) - (left.waited ?? UNKNOWN_WAIT) || this.byKey(left.task, right.task))
      .map(({ task, waited }) => ({
        key: `${task.project}/${task.slug}`,
        task,
        reason: (task.reason ?? NEEDS_HUMAN).replaceAll(REASON_WORD_SEPARATOR, ' '),
        waiting: waited === null ? '' : formatDuration(waited),
        question: task.question,
        visits: task.metrics.needsHumanCount > NO_COUNT ? `${task.metrics.needsHumanCount}× you` : '',
        command: `${ANSWER_COMMAND_PREFIX} ${task.slug} ${ANSWER_PLACEHOLDER}`,
      }));
  }

  /** Time since the task entered Needs human, from the earliest entry of the trailing run in that column; null when unknown. */
  waitedMilliseconds(task: BoardTask, nowMilliseconds: number): number | null {
    const leftAt = [...task.history].reverse().findIndex((entry) => entry.column !== NEEDS_HUMAN);

    const runLength = leftAt === NOT_FOUND ? task.history.length : leftAt;

    const first = runLength === NO_COUNT ? undefined : task.history[task.history.length - runLength];

    const since = first === undefined ? Number.NaN : Date.parse(first.ts);

    return Number.isFinite(since) ? Math.max(NO_COUNT, nowMilliseconds - since) : null;
  }

  /** Finished tasks, newest first. */
  doneRows(snapshot: BoardSnapshot, tasks: TaskSummary[], project: string | null): DoneRow[] {
    const summaries = this.summariesByKey(tasks);

    return this.tasksOf(snapshot, project)
      .filter((task) => this.columnOf(task) === DONE)
      .map((task) => ({ task, summary: summaries.get(`${task.project}/${task.slug}`) }))
      .sort((left, right) => (right.summary?.updatedAt ?? '').localeCompare(left.summary?.updatedAt ?? '') || this.byKey(left.task, right.task))
      .map(({ task, summary }) => {
        const cancelled = task.stage === STAGE_CANCELLED;

        const outcome = cancelled ? OUTCOME_CANCELLED : OUTCOME_MERGED;

        return {
          key: `${task.project}/${task.slug}`,
          task,
          cancelled,
          outcome,
          icon: OUTCOME_ICONS[outcome],
          time: summary && summary.agentMilliseconds > NO_COUNT ? formatDuration(summary.agentMilliseconds) : '',
        };
      });
  }

  /** The four totals tiles over the tasks of the shown project (every project when null). */
  totalTiles(snapshot: BoardSnapshot, tasks: TaskSummary[], project: string | null, nowMilliseconds: number): TotalsTile[] {
    const shown = this.tasksOf(snapshot, project);

    const agents = snapshot.agents.filter((agent) => project === null || agent.project === project);

    const agentNames = [...new Set(agents.map((agent) => this.agentName(agent)))];

    const waits = shown.filter((task) => this.columnOf(task) === NEEDS_HUMAN);

    const longestWait = Math.max(UNKNOWN_WAIT, ...waits.map((task) => this.waitedMilliseconds(task, nowMilliseconds) ?? UNKNOWN_WAIT));

    const tokens = tasks.filter((summary) => project === null || summary.project === project).reduce((sum, summary) => sum + summary.tokens.total, NO_COUNT);

    const openTasks = shown.filter((task) => this.columnOf(task) !== DONE).length;

    const manual = shown.reduce((sum, task) => sum + task.metrics.manualAcceptanceCriteria, NO_COUNT);

    return [
      { id: TILE_AGENTS, label: 'Agents working', value: String(agents.length), detail: agentNames.join(DETAIL_SEPARATOR) || NO_VALUE, tone: 'active' },
      { id: TILE_WAITING, label: 'Waiting for you', value: longestWait === UNKNOWN_WAIT ? NO_VALUE : formatDuration(longestWait), detail: pluralize(waits.length, 'task'), tone: 'human' },
      { id: TILE_TOKENS, label: 'Tokens', value: formatCount(tokens), detail: `across ${pluralize(openTasks, 'open task')}`, tone: '' },
      { id: TILE_MANUAL, label: 'Manual acceptance criteria', value: String(manual), detail: 'to check by hand before merge', tone: '' },
    ];
  }

  /** "All projects" first, then every project, each with its task count and the number of its tasks waiting for a human. */
  projectOptions(snapshot: BoardSnapshot): ProjectOption[] {
    const options = snapshot.projects.map((project) => ({
      value: project.name,
      label: project.name,
      count: project.tasks.length,
      waiting: project.tasks.filter((task) => this.columnOf(task) === NEEDS_HUMAN).length,
    }));

    const total = (key: 'count' | 'waiting') => options.reduce((sum, option) => sum + option[key], NO_COUNT);

    return [{ value: ALL_PROJECTS, label: ALL_PROJECTS_LABEL, count: total('count'), waiting: total('waiting') }, ...options];
  }

  searchProjectOptions(options: ProjectOption[], query: string): ProjectOption[] {
    const needle = query.trim().toLowerCase();

    return options.filter((option) => option.label.toLowerCase().includes(needle));
  }

  findTask(snapshot: BoardSnapshot | null, project: string, slug: string): BoardTask | null {
    return snapshot?.projects.flatMap((candidate) => candidate.tasks).find((task) => task.project === project && task.slug === slug) ?? null;
  }

  /** The columns the task has been through, in order, each with the time it stayed. */
  historyRows(task: BoardTask): HistoryRow[] {
    return task.durations.map(({ column, milliseconds }) => ({ column, duration: formatDuration(milliseconds) }));
  }

  private tasksOf(snapshot: BoardSnapshot, project: string | null): BoardTask[] {
    return snapshot.projects.filter((candidate) => project === null || candidate.name === project).flatMap((candidate) => candidate.tasks);
  }

  private summariesByKey(tasks: TaskSummary[]): Map<string, TaskSummary> {
    return new Map(tasks.map((summary) => [`${summary.project}/${summary.slug}`, summary]));
  }

  private agentName(agent: BoardAgent): string {
    return agent.agent_type.slice(agent.agent_type.lastIndexOf(AGENT_TYPE_SEPARATOR) + 1);
  }

  private byKey(left: BoardTask, right: BoardTask): number {
    return `${left.project}/${left.slug}`.localeCompare(`${right.project}/${right.slug}`);
  }

  /** Newest first; tasks without a timestamp go last, ties keep a stable slug order. */
  private byNewest(left: CardView, right: CardView, updatedAt: Map<string, string | null>): number {
    const leftTime = updatedAt.get(left.key) ?? '';

    const rightTime = updatedAt.get(right.key) ?? '';

    return rightTime.localeCompare(leftTime) || left.key.localeCompare(right.key);
  }

  private buildAgents(agents: BoardAgent[], task: BoardTask, nowMilliseconds: number): AgentView[] {
    return this.agentsWorkingOn(agents, task).map((agent) => ({ id: agent.tool_use_id, name: this.agentName(agent), elapsed: formatElapsed(nowMilliseconds - Date.parse(agent.ts)) }));
  }

  private buildCard(task: BoardTask, summary: TaskSummary | undefined, agents: BoardAgent[], nowMilliseconds: number): CardView {
    const inProgress = WORKING_COLUMNS.has(this.columnOf(task));

    const rounds = (summary?.rounds ?? []).map((round) => ({
      n: round.n,
      label: `R${round.n}`,
      chips: Object.entries(round.reviews).map(([reviewer, state]) => {
        const className = this.chipClassName(state, inProgress);

        return { reviewer, state, className, icon: CHIP_ICONS[className] };
      }),
    }));

    const risk = summary?.risk ?? null;

    const running = this.buildAgents(agents, task, nowMilliseconds);

    return {
      key: `${task.project}/${task.slug}`,
      task,
      active: running.length > NO_COUNT,
      risk,
      riskIcon: risk === null ? '' : RISK_ICONS[risk],
      rounds,
      agents: running,
      mrUrl: summary?.mrUrl ?? null,
      time: summary && summary.agentMilliseconds > NO_COUNT ? formatDuration(summary.agentMilliseconds) : '',
      tokens: summary && summary.tokens.total > NO_COUNT ? `${formatCount(summary.tokens.total)} tok` : '',
    };
  }
}

export default BoardView;
