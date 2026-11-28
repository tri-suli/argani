import type { PipelineColumn } from '@/types/view';

const COLUMN_INTAKE = 'Intake';

const COLUMN_SPEC = 'Spec';

const COLUMN_BUILD = 'Build';

const COLUMN_REVIEW = 'Review';

const COLUMN_APPROVE = 'Approve';

const NEEDS_HUMAN = 'Needs human';

const DONE = 'Done';

/** The factory pipeline's columns in order; each card's column comes from board.json. */
const PIPELINE: PipelineColumn[] = [
  { step: '01', name: COLUMN_INTAKE, who: 'intake' },
  { step: '02', name: COLUMN_SPEC, who: 'spec-writer' },
  { step: '03', name: COLUMN_BUILD, who: 'builder · verify' },
  { step: '04', name: COLUMN_REVIEW, who: 'reviewers' },
  { step: '05', name: COLUMN_APPROVE, who: 'approver · merge' },
];

/** Every column board.json may name; a task in any other column is shown as Needs human. */
const KNOWN_COLUMNS = new Set([...PIPELINE.map((column) => column.name), NEEDS_HUMAN, DONE]);

const STAGE_CANCELLED = 'cancelled';

const OUTCOME_MERGED = 'merged';

const OUTCOME_CANCELLED = 'cancelled';

const OUTCOME_ICONS: Record<string, string> = { [OUTCOME_MERGED]: 'merge', [OUTCOME_CANCELLED]: 'block' };

const ANSWER_COMMAND_PREFIX = '/argani:factory answer';

const ANSWER_PLACEHOLDER = '<answer>';

const WORKING_COLUMNS = new Set([COLUMN_BUILD, COLUMN_REVIEW]);

export {
  COLUMN_INTAKE,
  COLUMN_SPEC,
  COLUMN_BUILD,
  COLUMN_REVIEW,
  COLUMN_APPROVE,
  NEEDS_HUMAN,
  DONE,
  PIPELINE,
  KNOWN_COLUMNS,
  STAGE_CANCELLED,
  OUTCOME_MERGED,
  OUTCOME_CANCELLED,
  OUTCOME_ICONS,
  ANSWER_COMMAND_PREFIX,
  ANSWER_PLACEHOLDER,
  WORKING_COLUMNS,
};
