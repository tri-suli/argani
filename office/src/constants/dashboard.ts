import type { ProjectOption } from '@/types/view';

const CLOCK_INTERVAL_MILLISECONDS = 1000;

/** The title of the page on the board, and the end of it while a task is open. */
const APP_TITLE = 'Argani Office';

const TITLE_SEPARATOR = ' · ';

const BOARD_TITLE_SELECTOR = '[data-testid=board-title]';

const ALL_PROJECTS = '';

const ALL_PROJECTS_LABEL = 'All projects';

/** Stands in for the picked option until the first snapshot has listed the projects. */
const NO_PROJECT_OPTION: ProjectOption = { value: ALL_PROJECTS, label: ALL_PROJECTS_LABEL, count: 0, waiting: 0 };

/** Zero as a count, token total or duration in milliseconds. */
const NO_COUNT = 0;

/** What `findIndex` returns when nothing matches. */
const NOT_FOUND = -1;

/** Sorts below every real wait (which is never negative). */
const UNKNOWN_WAIT = -1;

/** Shown where a tile or row has nothing to say. */
const NO_VALUE = '—';

const AGENT_TYPE_SEPARATOR = ':';

const DETAIL_SEPARATOR = ' · ';

const REASON_WORD_SEPARATOR = '-';

// how long the Copy button keeps saying "Copied" (or "Copy failed") before it is a plain "Copy" again
const COPY_FEEDBACK_MILLISECONDS = 2000;

const COPY_LABEL = 'Copy';

const COPIED_LABEL = 'Copied';

const COPY_FAILED_LABEL = 'Copy failed';

const TILE_AGENTS = 'agents';

const TILE_WAITING = 'waiting';

const TILE_TOKENS = 'tokens';

const TILE_MANUAL = 'manual';

export {
  CLOCK_INTERVAL_MILLISECONDS,
  APP_TITLE,
  TITLE_SEPARATOR,
  BOARD_TITLE_SELECTOR,
  ALL_PROJECTS,
  ALL_PROJECTS_LABEL,
  NO_PROJECT_OPTION,
  NO_COUNT,
  NOT_FOUND,
  UNKNOWN_WAIT,
  NO_VALUE,
  AGENT_TYPE_SEPARATOR,
  DETAIL_SEPARATOR,
  REASON_WORD_SEPARATOR,
  COPY_FEEDBACK_MILLISECONDS,
  COPY_LABEL,
  COPIED_LABEL,
  COPY_FAILED_LABEL,
  TILE_AGENTS,
  TILE_WAITING,
  TILE_TOKENS,
  TILE_MANUAL,
};
