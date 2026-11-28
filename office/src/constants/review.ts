import type { ReviewOutcome, ReviewState, Risk } from '@/types/task';
import { ICON } from '@/constants/icons';

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
  PASS: ICON.check,
  CHANGES: ICON.priorityHigh,
  pending: ICON.moreHoriz,
  [CHIP_CLASS_WAITING]: ICON.hourglassTop,
  [CHIP_CLASS_INVALID]: ICON.error,
};

const RISK_ICONS: Record<Risk, string> = { low: ICON.shield, medium: ICON.warning, high: ICON.warning };

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
