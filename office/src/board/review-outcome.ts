import { REVIEW_OUTCOME_CHANGES, REVIEW_OUTCOME_PASS } from '@/constants/review';
import type { ReviewOutcome, TaskRound } from '@/types/task';

/** CHANGES when any reviewer asked for changes, PASS when every reviewer passed, otherwise not decided (null). */
function roundOutcome(round: TaskRound | undefined): ReviewOutcome | null {
  const states = Object.values(round?.reviews ?? {});

  if (states.includes(REVIEW_OUTCOME_CHANGES)) {
    return REVIEW_OUTCOME_CHANGES;
  }

  return states.length > 0 && states.every((state) => state === REVIEW_OUTCOME_PASS) ? REVIEW_OUTCOME_PASS : null;
}

export default roundOutcome;
