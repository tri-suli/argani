import type { PipelineColumn } from './types';

// Shorter than the poll interval: a backend that never answers must surface as a failure, not a hang.
export const DEFAULT_TIMEOUT_MILLISECONDS = 4000;

// Documents are read-only text: no form controls, images, embeds or styles; Alpine-looking attributes
// (x-*, @*, :*) are not in DOMPurify's allow list and so never survive.
export const SANITIZE_OPTIONS = {
  FORBID_TAGS: ['form', 'input', 'button', 'select', 'textarea', 'img', 'style', 'iframe', 'object', 'embed'],
  FORBID_ATTR: ['style'],
};

export const SUMMARY_HEADING = '## Summary';

/** The factory pipeline, fixed and independent of the plugin's own columns. */
export const PIPELINE: PipelineColumn[] = [
  { name: 'Intake', who: 'intent · you approve', tone: '' },
  { name: 'Spec', who: 'spec-writer', tone: '' },
  { name: 'Build', who: 'builder · verify', tone: '' },
  { name: 'Review', who: 'reviewers', tone: '' },
  { name: 'Approve', who: 'approver · you merge', tone: '' },
  { name: 'Needs human', who: 'you', tone: 'human' },
  { name: 'Done', who: 'merged', tone: 'merged' },
];

// Stage names come from plugins/argani/scripts/factory_state.py decide_stage; an unknown one lands in Needs human.
export const STAGE_COLUMN: Record<string, string> = {
  'needs-intent-approval': 'Intake',
  'needs-spec': 'Spec',
  'needs-spec-approval': 'Spec',
  'needs-build': 'Build',
  'needs-rework': 'Build',
  'needs-review': 'Review',
  'needs-decision': 'Approve',
  'needs-mr': 'Approve',
};

/** Stages whose next step is the human's, besides every card in Needs human. */
export const HUMAN_STAGES = new Set(['needs-intent-approval', 'needs-spec-approval']);

export const NEEDS_HUMAN = 'Needs human';
export const DONE = 'Done';
export const WORKING_COLUMNS = new Set(['Build', 'Review']);
