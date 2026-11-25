import type { PipelineColumn, ReviewState } from '@/board/types';

// Shorter than the poll interval: a backend that never answers must surface as a failure, not a hang.
const DEFAULT_TIMEOUT_MILLISECONDS = 4000;

const DEFAULT_POLL_INTERVAL_MILLISECONDS = 5000;

const MILLISECONDS_PER_SECOND = 1000;

const MILLISECONDS_PER_MINUTE = 60_000;

const MINUTES_PER_HOUR = 60;

const MINUTES_PAD_WIDTH = 2;

// counts below this are shown as they are; from here on they read in thousands ("6.0k")
const THOUSANDS_DISPLAY_THRESHOLD = 1000;

const COUNT_PER_THOUSAND = 1000;

const COUNT_PER_MILLION = 1_000_000;

// 999_950 would round to "1000.0k"; from here on counts are shown in millions
const MILLIONS_DISPLAY_THRESHOLD = 999_950;

const NOT_FOUND_INDEX = -1;

const ALL_PROJECTS = '';

const MARKDOWN_EXTENSION = '.md';

const PATH_SEPARATOR = '/';

const SECTION_HEADING_PREFIX = '## ';

const ANCHOR_TAG_NAME = 'A';

const HREF_ATTRIBUTE = 'href';

// Documents are read-only text: no form controls, images, embeds or styles; Alpine-looking attributes
// (x-*, @*, :*) are not in DOMPurify's allow list and so never survive.
const SANITIZE_OPTIONS = {
  FORBID_TAGS: ['form', 'input', 'button', 'select', 'textarea', 'img', 'style', 'iframe', 'object', 'embed'],
  FORBID_ATTR: ['style'],
};

const SUMMARY_HEADING = '## Summary';

const COLUMN_INTAKE = 'Intake';

const COLUMN_SPEC = 'Spec';

const COLUMN_BUILD = 'Build';

const COLUMN_REVIEW = 'Review';

const COLUMN_APPROVE = 'Approve';

const NEEDS_HUMAN = 'Needs human';

const DONE = 'Done';

const STAGE_DONE = 'done';

const STAGE_NEEDS_INTENT_APPROVAL = 'needs-intent-approval';

const STAGE_NEEDS_SPEC = 'needs-spec';

const STAGE_NEEDS_SPEC_APPROVAL = 'needs-spec-approval';

const STAGE_NEEDS_BUILD = 'needs-build';

const STAGE_NEEDS_REWORK = 'needs-rework';

const STAGE_NEEDS_REVIEW = 'needs-review';

const STAGE_NEEDS_DECISION = 'needs-decision';

const STAGE_NEEDS_MR = 'needs-mr';

const REVIEW_STATE_PENDING = 'pending' as const satisfies ReviewState;

const REVIEW_STATE_INVALID = 'invalid' as const satisfies ReviewState;

// Review chip classes: the state's own name, except these three.
const CHIP_CLASS_WAITING = 'wait';

const CHIP_CLASS_PENDING = 'pending';

const CHIP_CLASS_INVALID = 'bad';

/** The factory pipeline, fixed and independent of the plugin's own columns. */
const PIPELINE: PipelineColumn[] = [
  { name: COLUMN_INTAKE, who: 'intent · you approve', tone: '' },
  { name: COLUMN_SPEC, who: 'spec-writer', tone: '' },
  { name: COLUMN_BUILD, who: 'builder · verify', tone: '' },
  { name: COLUMN_REVIEW, who: 'reviewers', tone: '' },
  { name: COLUMN_APPROVE, who: 'approver · you merge', tone: '' },
  { name: NEEDS_HUMAN, who: 'you', tone: 'human' },
  { name: DONE, who: 'merged', tone: 'merged' },
];

// Stage names come from plugins/argani/scripts/factory_state.py decide_stage; an unknown one lands in Needs human.
const STAGE_COLUMN: Record<string, string> = {
  [STAGE_NEEDS_INTENT_APPROVAL]: COLUMN_INTAKE,
  [STAGE_NEEDS_SPEC]: COLUMN_SPEC,
  [STAGE_NEEDS_SPEC_APPROVAL]: COLUMN_SPEC,
  [STAGE_NEEDS_BUILD]: COLUMN_BUILD,
  [STAGE_NEEDS_REWORK]: COLUMN_BUILD,
  [STAGE_NEEDS_REVIEW]: COLUMN_REVIEW,
  [STAGE_NEEDS_DECISION]: COLUMN_APPROVE,
  [STAGE_NEEDS_MR]: COLUMN_APPROVE,
};

/** Stages whose next step is the human's, besides every card in Needs human. */
const HUMAN_STAGES = new Set([STAGE_NEEDS_INTENT_APPROVAL, STAGE_NEEDS_SPEC_APPROVAL]);

const WORKING_COLUMNS = new Set([COLUMN_BUILD, COLUMN_REVIEW]);

export {
  DEFAULT_TIMEOUT_MILLISECONDS,
  DEFAULT_POLL_INTERVAL_MILLISECONDS,
  MILLISECONDS_PER_SECOND,
  MILLISECONDS_PER_MINUTE,
  MINUTES_PER_HOUR,
  MINUTES_PAD_WIDTH,
  THOUSANDS_DISPLAY_THRESHOLD,
  COUNT_PER_THOUSAND,
  COUNT_PER_MILLION,
  MILLIONS_DISPLAY_THRESHOLD,
  NOT_FOUND_INDEX,
  ALL_PROJECTS,
  MARKDOWN_EXTENSION,
  PATH_SEPARATOR,
  SECTION_HEADING_PREFIX,
  ANCHOR_TAG_NAME,
  HREF_ATTRIBUTE,
  SANITIZE_OPTIONS,
  SUMMARY_HEADING,
  COLUMN_APPROVE,
  STAGE_DONE,
  REVIEW_STATE_PENDING,
  REVIEW_STATE_INVALID,
  CHIP_CLASS_WAITING,
  CHIP_CLASS_PENDING,
  CHIP_CLASS_INVALID,
  PIPELINE,
  STAGE_COLUMN,
  HUMAN_STAGES,
  NEEDS_HUMAN,
  DONE,
  WORKING_COLUMNS,
};
