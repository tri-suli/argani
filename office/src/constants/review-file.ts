import type { FindingPartKind, FindingSeverity } from '@/types/review-file';
import type { ReviewOutcome } from '@/types/task';

/** The closing line of a review file (plugins/argani/scripts/factory_state.py, CLOSING_REVIEW). */
const CLOSING_LINE = '=== END OF REVIEW ===';

const BYTE_ORDER_MARK = /^﻿/;

const LINE_ENDINGS = /\r\n?/g;

const LINE_BREAK = '\n';

/** Line 1: the verdict word, then an optional reason. */
const VERDICT_WORDS: Record<string, ReviewOutcome> = { PASS: 'PASS', CHANGES: 'CHANGES' };

const VERDICT_LINE = /^(\S+)\s*(.*)$/;

/** A finding bullet: "- [Severity] rest", also as an ordered list item ("1. [Severity] rest"). */
const FINDING_START = /^(?:[-*+]|\d+[.)])[ \t]+\[([^\]\n]*)\][ \t]*(.*)$/;

/** A line that ends the finding above it even without a blank line: a heading, a list item, a quote, a rule. */
const BLOCK_START = /^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|(?:-{3,}|\*{3,}|_{3,})\s*$)/;

/** The opening line of a fenced code block, indented or not. */
const FENCE_OPENING = /^\s*(`{3,}|~{3,})/;

const FENCE_CLOSING = /^\s*(`{3,}|~{3,})\s*$/;

/** A line that continues the bullet above it. */
const INDENTED_LINE = /^[ \t]+\S/;

const LEADING_WHITESPACE = /^[ \t]*/;

const SEVERITY_IMPORTANT = 'important' as const satisfies FindingSeverity;

const SEVERITY_NIT = 'nit' as const satisfies FindingSeverity;

const SEVERITY_OTHER = 'other' as const satisfies FindingSeverity;

const PART_TEXT = 'text' as const satisfies FindingPartKind;

const PART_FIX = 'fix' as const satisfies FindingPartKind;

const SEVERITIES: Record<string, Exclude<FindingSeverity, typeof SEVERITY_OTHER>> = { important: SEVERITY_IMPORTANT, nit: SEVERITY_NIT };

const SEVERITY_LABELS: Record<Exclude<FindingSeverity, typeof SEVERITY_OTHER>, string> = { [SEVERITY_IMPORTANT]: 'Important', [SEVERITY_NIT]: 'Nit' };

const LABEL_KINDS: Record<string, FindingPartKind> = { What: 'what', Why: 'why', Fix: 'fix' };

/** A label opens a part only at a word start and with a space or the end after the colon. */
const PART_LABEL = /(What|Why|Fix):(?=\s|$)/y;

const WHITESPACE = /\s/;

/** The text before the first label names the location only when a dash closes it: "src/a.php:12 -". */
const LOCATION_BEFORE_DASH = /^(.+?)\s+[-–—]$/;

const CODE_SPAN_WRAPPER = /^`([^`]+)`$/;

const BACKTICK = '`';

const NOT_FOUND = -1;

const FULL_PART_COUNT = 3;

export {
  SEVERITY_IMPORTANT,
  SEVERITY_NIT,
  SEVERITY_OTHER,
  PART_TEXT,
  PART_FIX,
  CLOSING_LINE,
  BYTE_ORDER_MARK,
  LINE_ENDINGS,
  LINE_BREAK,
  VERDICT_WORDS,
  VERDICT_LINE,
  FINDING_START,
  BLOCK_START,
  FENCE_OPENING,
  FENCE_CLOSING,
  INDENTED_LINE,
  LEADING_WHITESPACE,
  SEVERITIES,
  SEVERITY_LABELS,
  LABEL_KINDS,
  PART_LABEL,
  WHITESPACE,
  LOCATION_BEFORE_DASH,
  CODE_SPAN_WRAPPER,
  BACKTICK,
  NOT_FOUND,
  FULL_PART_COUNT,
};
