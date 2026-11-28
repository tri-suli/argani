import { HUMAN_REVIEWER, REVIEW_OUTCOME_CHANGES, REVIEW_OUTCOME_PASS, REVIEW_STATE_PENDING } from '@/constants/review';
import type { ReviewOutcome, TaskRound } from '@/types/task';

/**
 * CHANGES when any reviewer asked for changes, PASS when every reviewer passed, otherwise not decided (null).
 * While the task is at work (`isWorking`), the request of the human alone does not decide a round whose reviewer seats have not all reported.
 */
function roundOutcome(round: TaskRound | undefined, isWorking = false): ReviewOutcome | null {
  const reviews = round?.reviews ?? {};

  const states = Object.values(reviews);

  if (states.includes(REVIEW_OUTCOME_CHANGES)) {
    const seats = Object.entries(reviews).filter(([name]) => name !== HUMAN_REVIEWER).map(([, state]) => state);

    return isWorking && !seats.includes(REVIEW_OUTCOME_CHANGES) && seats.includes(REVIEW_STATE_PENDING) ? null : REVIEW_OUTCOME_CHANGES;
  }

  return states.length > 0 && states.every((state) => state === REVIEW_OUTCOME_PASS) ? REVIEW_OUTCOME_PASS : null;
}

export default roundOutcome;
