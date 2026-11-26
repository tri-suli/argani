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
  { name: COLUMN_INTAKE, who: 'intake', tone: '' },
  { name: COLUMN_SPEC, who: 'spec-writer', tone: '' },
  { name: COLUMN_BUILD, who: 'builder · verify', tone: '' },
  { name: COLUMN_REVIEW, who: 'reviewers', tone: '' },
  { name: COLUMN_APPROVE, who: 'approver · merge', tone: '' },
  { name: NEEDS_HUMAN, who: 'you', tone: 'human' },
  { name: DONE, who: 'merged', tone: 'merged' },
];

const PIPELINE_NAMES = new Set(PIPELINE.map((column) => column.name));

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
  PIPELINE_NAMES,
  WORKING_COLUMNS,
};
