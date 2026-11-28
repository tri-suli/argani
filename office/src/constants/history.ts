import { REVIEW_OUTCOME_CHANGES, REVIEW_OUTCOME_PASS } from '@/constants/review';
import type { LegendEntry, StepKind } from '@/types/history';
import type { ReviewOutcome } from '@/types/task';

const STEP_AGENT = 'agent' as const satisfies StepKind;

const STEP_HUMAN = 'human' as const satisfies StepKind;

const STEP_CHANGES = 'changes' as const satisfies StepKind;

const STEP_PASS = 'pass' as const satisfies StepKind;

const STEP_NOW = 'now' as const satisfies StepKind;

const STEP_CANCELLED = 'cancelled' as const satisfies StepKind;

/** The colour legend of the history strip, in the order of the design. */
const STEP_LEGEND: LegendEntry[] = [
  { kind: STEP_AGENT, label: 'agent worked' },
  { kind: STEP_HUMAN, label: 'waited for you' },
  { kind: STEP_CHANGES, label: 'changes asked' },
  { kind: STEP_PASS, label: 'passed' },
  { kind: STEP_NOW, label: 'now' },
  { kind: STEP_CANCELLED, label: 'cancelled' },
];

const OUTCOME_CHANGES_NOTE = 'changes asked';

const OUTCOME_PASS_NOTE = 'passed';

const OUTCOME_KINDS: Record<ReviewOutcome, StepKind> = { [REVIEW_OUTCOME_CHANGES]: STEP_CHANGES, [REVIEW_OUTCOME_PASS]: STEP_PASS };

const OUTCOME_NOTES: Record<ReviewOutcome, string> = { [REVIEW_OUTCOME_CHANGES]: OUTCOME_CHANGES_NOTE, [REVIEW_OUTCOME_PASS]: OUTCOME_PASS_NOTE };

const RUNNING_NOTE = 'running';

const NOTE_SEPARATOR = ' · ';

const REVIEW_ROUND_PREFIX = 'R';

export {
  STEP_AGENT,
  STEP_HUMAN,
  STEP_CHANGES,
  STEP_PASS,
  STEP_NOW,
  STEP_CANCELLED,
  STEP_LEGEND,
  OUTCOME_KINDS,
  OUTCOME_NOTES,
  RUNNING_NOTE,
  NOTE_SEPARATOR,
  REVIEW_ROUND_PREFIX,
};
