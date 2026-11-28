/** The hash of the board: no hash at all. */
const BOARD_HASH = '';

const TASK_HASH_PREFIX = '#/task/';

const ROUTE_SEPARATOR = '/';

/** Segments after the prefix: project and slug, plus an optional file. */
const MIN_ROUTE_SEGMENTS = 2;

const MAX_ROUTE_SEGMENTS = 3;

const FILE_SEGMENT_INDEX = 2;

const POP_STATE_EVENT = 'popstate';

export {
  BOARD_HASH,
  TASK_HASH_PREFIX,
  ROUTE_SEPARATOR,
  MIN_ROUTE_SEGMENTS,
  MAX_ROUTE_SEGMENTS,
  FILE_SEGMENT_INDEX,
  POP_STATE_EVENT,
};
