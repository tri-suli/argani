import type { PipelineColumn } from '@/types/view';

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
  COLUMN_INTAKE,
  COLUMN_SPEC,
  COLUMN_BUILD,
  COLUMN_REVIEW,
  COLUMN_APPROVE,
  NEEDS_HUMAN,
  DONE,
  STAGE_DONE,
  STAGE_NEEDS_INTENT_APPROVAL,
  STAGE_NEEDS_SPEC,
  STAGE_NEEDS_SPEC_APPROVAL,
  STAGE_NEEDS_BUILD,
  STAGE_NEEDS_REWORK,
  STAGE_NEEDS_REVIEW,
  STAGE_NEEDS_DECISION,
  STAGE_NEEDS_MR,
  PIPELINE,
  STAGE_COLUMN,
  HUMAN_STAGES,
  WORKING_COLUMNS,
};
