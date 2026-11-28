import { RUNNING_ICON } from '@/constants/file-tree';
import type { FindingFilter, RoundStatus } from '@/types/round';
import type { FindingPartKind, FindingSeverity } from '@/types/review-file';

const SUMMARY_SEPARATOR = ' · ';

/** A link inside the text of a finding that points at a fragment: the address hash is the route, so it must not follow it. */
const FRAGMENT_LINK_SELECTOR = 'a[href^="#"]';

/** The checklist name the human's request is filed under: `review-human.md`. */
const HUMAN_REVIEWER = 'human';

const MODEL_INHERIT = 'inherit';

/** "review-code.md" names the reviewer "code". */
const REVIEW_FILE_NAME = /^review-(.+)\.md$/;

const ROUND_TITLE_PREFIX = 'Round';

const ROUND_GROUP_PREFIX = 'Round ';

const PART_LABELS: Record<FindingPartKind, string> = { what: 'What', why: 'Why', fix: 'Fix', text: '' };

const SEVERITY_ICONS: Record<FindingSeverity, string> = { important: 'priority_high', nit: 'info', other: 'help' };

/** Important first, then nits, then what the protocol does not define. */
const SEVERITY_RANK: Record<FindingSeverity, number> = { important: 0, nit: 1, other: 2 };

const FILTER_SEVERITY: Record<Exclude<FindingFilter, 'all'>, FindingSeverity> = { important: 'important', nit: 'nit' };

const FILTER_CHIPS: { filter: FindingFilter; label: string }[] = [
  { filter: 'all', label: 'All' },
  { filter: 'important', label: 'Important' },
  { filter: 'nit', label: 'Nits' },
];

const FILTER_ALL = 'all' as const satisfies FindingFilter;

const STATUS_RUNNING: RoundStatus = { label: 'RUNNING', icon: RUNNING_ICON, tone: 'now', spinning: true, toneLabel: 'running' };

const STATUS_UNDECIDED: RoundStatus = { label: 'UNDECIDED', icon: 'hourglass_top', tone: 'none', spinning: false, toneLabel: 'not decided yet' };

const STATUS_NOT_REPORTED: RoundStatus = { label: 'NOT REPORTED', icon: 'more_horiz', tone: 'none', spinning: false, toneLabel: 'has not reported' };

const STATUS_INVALID: RoundStatus = { label: 'INVALID', icon: 'cancel', tone: 'stop', spinning: false, toneLabel: 'no valid verdict' };

const MESSAGE_NOT_REPORTED = 'Has not reported yet.';

const MESSAGE_UNREADABLE = 'This file could not be read.';

const MESSAGE_NO_FINDINGS_YET = 'No findings yet. This page fills in as each reviewer finishes.';

const MESSAGE_NO_FINDING = 'No finding cards in this round.';

const MESSAGE_NOTES_BELOW = ' The notes of the reviewers are below.';

const MESSAGE_NOTES_UNDER_ALL = ' The notes of the reviewers are under All.';

const NOTES_TITLE_PREFIX = 'Notes from ';

const NOTES_TITLE_HUMAN = 'Notes from the human';

const NOTE_SENTENCE = 'Also holds text that is not a finding: shown below the findings.';

const MESSAGE_SOME_PENDING = ' yet. Some reviewers have not reported.';

const SENTENCE_END = '.';

const EMPTY_FILTER_MESSAGES: Record<Exclude<FindingFilter, 'all'>, string> = { important: 'No important finding in this round', nit: 'No nits in this round' };

export {
  SUMMARY_SEPARATOR,
  FRAGMENT_LINK_SELECTOR,
  HUMAN_REVIEWER,
  MODEL_INHERIT,
  REVIEW_FILE_NAME,
  ROUND_TITLE_PREFIX,
  ROUND_GROUP_PREFIX,
  PART_LABELS,
  SEVERITY_ICONS,
  SEVERITY_RANK,
  FILTER_SEVERITY,
  FILTER_CHIPS,
  FILTER_ALL,
  STATUS_RUNNING,
  STATUS_UNDECIDED,
  STATUS_NOT_REPORTED,
  STATUS_INVALID,
  MESSAGE_NOT_REPORTED,
  MESSAGE_UNREADABLE,
  MESSAGE_NO_FINDINGS_YET,
  MESSAGE_NO_FINDING,
  MESSAGE_NOTES_BELOW,
  MESSAGE_NOTES_UNDER_ALL,
  NOTES_TITLE_PREFIX,
  NOTES_TITLE_HUMAN,
  NOTE_SENTENCE,
  MESSAGE_SOME_PENDING,
  SENTENCE_END,
  EMPTY_FILTER_MESSAGES,
};
