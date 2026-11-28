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

export type { StepKind, HistoryStep, LegendEntry };
