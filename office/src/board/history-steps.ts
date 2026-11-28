import { formatDuration, formatElapsed } from '@/board/format';
import roundOutcome from '@/board/review-outcome';
import { NO_COUNT, REASON_WORD_SEPARATOR } from '@/constants/dashboard';
import { NOTE_SEPARATOR, OUTCOME_CHANGES_NOTE, OUTCOME_PASS_NOTE, REVIEW_ROUND_PREFIX, RUNNING_NOTE, STEP_AGENT, STEP_CHANGES, STEP_HUMAN, STEP_NOW, STEP_PASS } from '@/constants/history';
import { COLUMN_REVIEW, DONE, NEEDS_HUMAN, OUTCOME_CANCELLED, OUTCOME_MERGED, STAGE_CANCELLED } from '@/constants/pipeline';
import { REVIEW_OUTCOME_CHANGES, REVIEW_OUTCOME_PASS } from '@/constants/review';
import type { BoardTask } from '@/types/board';
import type { HistoryStep, StepKind } from '@/types/history';
import type { ReviewOutcome, TaskSummary } from '@/types/task';

/** The entries of one column, back to back in the task's history. */
interface Run {
  column: string;
  startedAt: string;
  reason: string | null;
  milliseconds: number;
}

const OUTCOME_KINDS: Record<ReviewOutcome, StepKind> = { [REVIEW_OUTCOME_CHANGES]: STEP_CHANGES, [REVIEW_OUTCOME_PASS]: STEP_PASS };

const OUTCOME_NOTES: Record<ReviewOutcome, string> = { [REVIEW_OUTCOME_CHANGES]: OUTCOME_CHANGES_NOTE, [REVIEW_OUTCOME_PASS]: OUTCOME_PASS_NOTE };

/** The stages a task has been through, from the history entries the board records; nothing is shown that the data does not state. */
class HistorySteps {
  /** One step per run of the same column, oldest first; the last step of an open task is "now". Empty without history. */
  derive(task: BoardTask, summary: TaskSummary | null, nowMilliseconds: number): HistoryStep[] {
    const runs = this.runsOf(task);

    let reviewVisits = NO_COUNT;

    // an interrupted review keeps its round number, so visits and rounds only line up when their counts are equal
    const visitsMatchRounds = summary !== null && summary.rounds.length === runs.filter((run) => run.column === COLUMN_REVIEW).length;

    return runs.map((run, index) => {
      const isLast = index === runs.length - 1;

      const step = run.column === COLUMN_REVIEW ? this.reviewStep(run, ++reviewVisits, visitsMatchRounds ? summary : null) : this.plainStep(run, task);

      return { ...this.withNumber(step, index), ...(isLast ? this.lastStepOf(step, run, task, nowMilliseconds) : {}) };
    });
  }

  private withNumber(step: Omit<HistoryStep, 'number'>, index: number): HistoryStep {
    return { number: String(index + 1), ...step };
  }

  /** Consecutive entries of one column are one run; each entry lasts until the next (the last until the board was computed). */
  private runsOf(task: BoardTask): Run[] {
    const runs: Run[] = [];

    task.history.forEach((entry, index) => {
      const recorded = task.durations[index]?.milliseconds ?? NO_COUNT;

      const milliseconds = Number.isFinite(recorded) ? recorded : NO_COUNT;

      const previous = runs.at(-1);

      if (previous?.column === entry.column) {
        previous.milliseconds += milliseconds;

        previous.reason ??= entry.reason;
      } else {
        runs.push({ column: entry.column, startedAt: entry.ts, reason: entry.reason, milliseconds });
      }
    });

    return runs;
  }

  private plainStep(run: Run, task: BoardTask): Omit<HistoryStep, 'number'> {
    if (run.column === NEEDS_HUMAN) {
      const reason = run.reason?.replaceAll(REASON_WORD_SEPARATOR, ' ');

      return { name: run.column, kind: STEP_HUMAN, note: this.joinNote(formatDuration(run.milliseconds), reason) };
    }

    if (run.column === DONE) {
      const merged = task.stage !== STAGE_CANCELLED;

      return { name: run.column, kind: merged ? STEP_PASS : STEP_AGENT, note: merged ? OUTCOME_MERGED : OUTCOME_CANCELLED };
    }

    return { name: run.column, kind: STEP_AGENT, note: formatDuration(run.milliseconds) };
  }

  /** The n-th visit to Review is review round n, when the summary lists exactly as many rounds as there were visits. */
  private reviewStep(run: Run, visit: number, summary: TaskSummary | null): Omit<HistoryStep, 'number'> {
    const round = summary?.rounds.find((candidate) => candidate.n === visit);

    if (round === undefined) {
      return { name: run.column, kind: STEP_AGENT, note: formatDuration(run.milliseconds) };
    }

    const outcome = roundOutcome(round);

    return {
      name: `${run.column} ${REVIEW_ROUND_PREFIX}${visit}`,
      kind: outcome === null ? STEP_AGENT : OUTCOME_KINDS[outcome],
      note: this.joinNote(formatDuration(run.milliseconds), outcome === null ? undefined : OUTCOME_NOTES[outcome]),
    };
  }

  /** The last step of a task that is not done is the one happening now; a wait for the human stays a wait, with the time ticking. */
  private lastStepOf(step: Omit<HistoryStep, 'number'>, run: Run, task: BoardTask, nowMilliseconds: number): Partial<HistoryStep> {
    if (task.column === DONE || run.column === DONE) {
      return {};
    }

    const started = Date.parse(run.startedAt);

    const elapsed = Number.isFinite(started) ? formatElapsed(nowMilliseconds - started) : run.milliseconds > NO_COUNT ? formatDuration(run.milliseconds) : undefined;

    if (run.column === NEEDS_HUMAN) {
      return { note: this.joinNote(elapsed, run.reason?.replaceAll(REASON_WORD_SEPARATOR, ' ')) || step.note };
    }

    return { kind: STEP_NOW, note: this.joinNote(RUNNING_NOTE, elapsed) };
  }

  private joinNote(...parts: (string | undefined)[]): string {
    return parts.filter((part) => part !== undefined && part !== '').join(NOTE_SEPARATOR);
  }
}

export default HistorySteps;
