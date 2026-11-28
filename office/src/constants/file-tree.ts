import { REVIEW_OUTCOME_CHANGES, REVIEW_OUTCOME_PASS } from '@/constants/review';
import type { RowTone } from '@/types/file-tree';
import type { FileTone, ReviewOutcome } from '@/types/task';

const TONE_NONE = 'none' as const satisfies RowTone;

const TONE_NOW = 'now' as const satisfies RowTone;

const FILE_TONE_ICONS: Record<FileTone, string> = { good: 'check_circle', warn: 'error', stop: 'cancel' };

const NO_TONE_ICON = 'description';

const DIFF_ICON = 'difference';

const DIFF_FILE_NAME = 'change.diff';

const RUNNING_ICON = 'progress_activity';

const ROUND_OUTCOME_TONES: Record<ReviewOutcome, FileTone> = { [REVIEW_OUTCOME_CHANGES]: 'warn', [REVIEW_OUTCOME_PASS]: 'good' };

const RUNNING_TAG = 'running';

const TONE_LABELS: Record<FileTone, string> = { good: 'passed', warn: 'changes requested', stop: 'escalated' };

const RUNNING_LABEL = 'running';

/** "Round 2" as the server names the group of the files of review round 2. */
const ROUND_GROUP_PATTERN = /^Round (\d+)$/;

const ROUND_LABEL_PREFIX = 'Round';

/** The heading over the review rounds; the server names no group for them as a whole. */
const REVIEW_SECTION_NAME = 'Review';

const WORD_SEPARATOR = /\s+/;

export {
  TONE_NONE,
  TONE_NOW,
  FILE_TONE_ICONS,
  NO_TONE_ICON,
  DIFF_ICON,
  DIFF_FILE_NAME,
  RUNNING_ICON,
  ROUND_OUTCOME_TONES,
  RUNNING_TAG,
  TONE_LABELS,
  RUNNING_LABEL,
  ROUND_GROUP_PATTERN,
  ROUND_LABEL_PREFIX,
  REVIEW_SECTION_NAME,
  WORD_SEPARATOR,
};
