import type { BoardTotals } from '@/types/view';

const CLOCK_INTERVAL_MILLISECONDS = 1000;

const ALL_PROJECTS = '';

/** Zero as a count, token total or duration in milliseconds. */
const NO_COUNT = 0;

const NO_TOTALS: BoardTotals = { manualAcceptanceCriteria: 0, needsHumanMilliseconds: 0 };

export {
  CLOCK_INTERVAL_MILLISECONDS,
  ALL_PROJECTS,
  NO_COUNT,
  NO_TOTALS,
};
