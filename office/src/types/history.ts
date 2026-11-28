/** What a step of the task history was: the colour and the legend entry it gets. */
type StepKind = 'agent' | 'human' | 'changes' | 'pass' | 'now' | 'cancelled';

interface HistoryStep {
  /** "1", "2", ...: the position, oldest first. */
  number: string;
  name: string;
  kind: StepKind;
  /** The time it stayed, with the reason or outcome when the data has one. */
  note: string;
}

interface LegendEntry {
  kind: StepKind;
  label: string;
}

/** The entries of one column, back to back in the task's history. */
interface Run {
  column: string;
  startedAt: string;
  /** The first reason of the run: the one a past wait is shown with. */
  reason: string | null;
  /** The latest reason of the run: the one the wait going on now is shown with, as on the board row. */
  latestReason: string | null;
  milliseconds: number;
}
export type { Run, StepKind, HistoryStep, LegendEntry };
