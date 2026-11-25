import type { ReviewState } from '@/types/task';

const REVIEW_STATE_PENDING = 'pending' as const satisfies ReviewState;

const REVIEW_STATE_INVALID = 'invalid' as const satisfies ReviewState;

// Review chip classes: the state's own name, except these three.
const CHIP_CLASS_WAITING = 'wait';

const CHIP_CLASS_PENDING = 'pending';

const CHIP_CLASS_INVALID = 'bad';

export {
  REVIEW_STATE_PENDING,
  REVIEW_STATE_INVALID,
  CHIP_CLASS_WAITING,
  CHIP_CLASS_PENDING,
  CHIP_CLASS_INVALID,
};
