import type { ReviewOutcome, ReviewState, Risk } from '@/types/task';

const REVIEW_STATE_PENDING = 'pending' as const satisfies ReviewState;

const REVIEW_OUTCOME_PASS = 'PASS' as const satisfies ReviewOutcome;

const REVIEW_OUTCOME_CHANGES = 'CHANGES' as const satisfies ReviewOutcome;

/** The checklist name the human's request is filed under: `review-human.md`. It is no reviewer seat. */
const HUMAN_REVIEWER = 'human';

const REVIEW_STATE_INVALID = 'invalid' as const satisfies ReviewState;

// Review chip classes: the state's own name, except these three.
const CHIP_CLASS_WAITING = 'wait';

const CHIP_CLASS_PENDING = 'pending';

const CHIP_CLASS_INVALID = 'bad';

// Icon-font ligatures: the chip state and the risk are never carried by colour alone.
const CHIP_ICONS: Record<string, string> = {
  PASS: 'check',
  CHANGES: 'priority_high',
  pending: 'more_horiz',
  [CHIP_CLASS_WAITING]: 'hourglass_top',
  [CHIP_CLASS_INVALID]: 'error',
};

const RISK_ICONS: Record<Risk, string> = { low: 'shield', medium: 'warning', high: 'warning' };

export {
  REVIEW_OUTCOME_PASS,
  REVIEW_OUTCOME_CHANGES,
  REVIEW_STATE_PENDING,
  HUMAN_REVIEWER,
  REVIEW_STATE_INVALID,
  CHIP_CLASS_WAITING,
  CHIP_CLASS_PENDING,
  CHIP_CLASS_INVALID,
  CHIP_ICONS,
  RISK_ICONS,
};
