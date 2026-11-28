/** The hash of the board: no hash at all. */
const BOARD_HASH = '';

const TASK_HASH_PREFIX = '#/task/';

const ROUTE_SEPARATOR = '/';

/** Segments after the prefix: project and slug, plus an optional file, or "round/<n>" for the overview of a review round. */
const MIN_ROUTE_SEGMENTS = 2;

const MAX_ROUTE_SEGMENTS = 4;

const FILE_SEGMENT_INDEX = 2;

const ROUND_SEGMENT_COUNT = 4;

const ROUND_SEGMENT = 'round';

/** The round of a route whose number is no round number ("round/0", "round/x"): no round has it, so the task opens at its first file. */
const NO_SUCH_ROUND = 0;

/** A round number as written by the address: no sign, no leading zero. */
const ROUND_NUMBER_PATTERN = /^[1-9]\d*$/;

const POP_STATE_EVENT = 'popstate';

const FROM_BOARD_KEY = 'fromBoard';

export {
  BOARD_HASH,
  TASK_HASH_PREFIX,
  ROUTE_SEPARATOR,
  MIN_ROUTE_SEGMENTS,
  MAX_ROUTE_SEGMENTS,
  FILE_SEGMENT_INDEX,
  ROUND_SEGMENT_COUNT,
  ROUND_SEGMENT,
  ROUND_NUMBER_PATTERN,
  NO_SUCH_ROUND,
  POP_STATE_EVENT,
  FROM_BOARD_KEY,
};
