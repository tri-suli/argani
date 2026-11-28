const META_LINE_PATTERN = /^([A-Za-z][A-Za-z ]{0,30}): (\S.*)$/;

// The keys of the `Key: value` block: Author, Status, Risk and Date (templates/intent.md), Intent (templates/spec.md),
// Spec (templates/plan.md and build.md), Round (the decision, factory_state.py ROUND_LINE) and MR, Opened and Merged (mr.md,
// factory_actions.py). Any other `Key: value` line is prose.
const META_KEYS = ['Author', 'Status', 'Risk', 'Date', 'Intent', 'Spec', 'Round', 'MR', 'Opened', 'Merged'];

const TITLE_PREFIX = '# ';

const BYTE_ORDER_MARK_PATTERN = /^\uFEFF/;

const NEWLINE_PATTERN = /\r\n?/g;

const LINE_BREAK = '\n';

const STATUS_KEY = 'Status';

const APPROVED_STATUS_PREFIX = 'approved';

const DOCUMENT_ID_PREFIX = 'doc-';

const FALLBACK_SECTION_SLUG = 'section';

const NON_SLUG_PATTERN = /[^\p{L}\p{N}]+/gu;

const EDGE_DASH_PATTERN = /^-+|-+$/g;

const SLUG_SEPARATOR = '-';

const MAX_HEADING_DEPTH = 6;

// an opening or closing h1-h6 tag of raw html, with the character that ends its name
const RAW_HEADING_TAG_PATTERN = /<(\/?)h([1-6])(?=[\s>/])/gi;

// marked token types
const TOKEN_HEADING = 'heading';

const TOKEN_CODE = 'code';

const TOKEN_LIST = 'list';

const TOKEN_HTML = 'html';

const MAX_OUTLINE_DEPTH = 3;

const SECTION_DEPTH = 2;

const SUMMARY_TITLE = 'Summary';

// plugins/argani/templates/intent.md: the section that holds the numbered criteria
const ACCEPTANCE_CRITERIA_TITLE = 'Acceptance criteria';

// plugins/argani/scripts/artifact_check.py AC_ITEM_PATTERN: `n. [ ] <claim> — verify: <how>`
const CRITERION_PATTERN = /^(\d+)\. \[([ xX])\] (.+) — verify: (\S.*)$/;

const CHECKED_BOX = 'x';

// artifact_check.py MANUAL_PREFIX: `verify: manual: <step>` marks a criterion only a human can check
const MANUAL_PREFIX_PATTERN = /^`?manual:\s*/i;

const CRITERION_ID_PREFIX = 'AC-';

const COMMENT_PATTERN = /<!--[\s\S]*?-->/g;

const WHITESPACE_PATTERN = /\s+/;

const WORDS_PER_MINUTE = 230;

const MINIMUM_READ_MINUTES = 1;

const ANCHOR_ATTRIBUTE = 'data-document-anchor';

const ANCHOR_SELECTOR = `a[${ANCHOR_ATTRIBUTE}]`;

const TABINDEX_ATTRIBUTE = 'tabindex';

// focusable by a script, not by the Tab key
const PROGRAMMATIC_FOCUS_ONLY = '-1';

const FRAGMENT_PREFIX = '#';

// the band of the viewport, from its top, in which a heading counts as the one being read
const READING_ZONE_PERCENT = 35;

const READING_ZONE_MARGIN = `0px 0px -${100 - READING_ZONE_PERCENT}% 0px`;

const PERCENT = 100;

// no scroll event for this long: the scrolling has settled
const SCROLL_SETTLE_MILLISECONDS = 150;

// a page scrolled to within this many pixels of its end counts as at its end (fractional scroll positions)
const PAGE_END_TOLERANCE_PIXELS = 2;

const SMOOTH_SCROLL = 'smooth';

const INSTANT_SCROLL = 'auto';

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

// where a heading is in relation to the reading zone
const IN_ZONE = 'zone';

const PASSED = 'above';

const NOT_REACHED = 'below';

const NOT_FOUND_INDEX = -1;

const FIRST_INDEX = 0;

// how many lines of a diff are put in the page; the rest is counted and named in a note
const DIFF_ROW_LIMIT = 1500;

const DIFF_FILE_START = 'diff ';

const DIFF_FILE_MARKERS = ['--- ', '+++ '];

const DIFF_HUNK_START = '@@';

const DIFF_ADD_MARKER = '+';

const DIFF_REMOVE_MARKER = '-';

const DIFF_NOTE_MARKER = '\\';

const DIFF_BINARY_STARTS = ['Binary files ', 'GIT binary patch'];

const DIFF_EXTENSION = '.diff';

const TRAILING_CARRIAGE_RETURN = /\r$/;

// `Status: approved by <name> on <date>`: the pill names who approved, the Date line carries the day
const STATUS_DATE_SUFFIX_PATTERN = / on \d{4}-\d{2}-\d{2}$/;

const TRAILING_NEWLINES_PATTERN = /\n+$/;

// a status without a tone yet: a draft
const NEUTRAL_STATUS_ICON = 'edit_note';

const INFO_STRING_SEPARATOR = /\s+/;

const HEADING_OPENING_PATTERN = /^<h(\d)>/;

export {
  META_LINE_PATTERN,
  META_KEYS,
  TITLE_PREFIX,
  BYTE_ORDER_MARK_PATTERN,
  NEWLINE_PATTERN,
  LINE_BREAK,
  STATUS_KEY,
  APPROVED_STATUS_PREFIX,
  DOCUMENT_ID_PREFIX,
  FALLBACK_SECTION_SLUG,
  NON_SLUG_PATTERN,
  EDGE_DASH_PATTERN,
  SLUG_SEPARATOR,
  MAX_HEADING_DEPTH,
  RAW_HEADING_TAG_PATTERN,
  TOKEN_HEADING,
  TOKEN_CODE,
  TOKEN_LIST,
  TOKEN_HTML,
  MAX_OUTLINE_DEPTH,
  SECTION_DEPTH,
  SUMMARY_TITLE,
  ACCEPTANCE_CRITERIA_TITLE,
  CRITERION_PATTERN,
  CHECKED_BOX,
  MANUAL_PREFIX_PATTERN,
  CRITERION_ID_PREFIX,
  COMMENT_PATTERN,
  WHITESPACE_PATTERN,
  WORDS_PER_MINUTE,
  MINIMUM_READ_MINUTES,
  ANCHOR_ATTRIBUTE,
  ANCHOR_SELECTOR,
  TABINDEX_ATTRIBUTE,
  PROGRAMMATIC_FOCUS_ONLY,
  FRAGMENT_PREFIX,
  READING_ZONE_PERCENT,
  READING_ZONE_MARGIN,
  PERCENT,
  SCROLL_SETTLE_MILLISECONDS,
  PAGE_END_TOLERANCE_PIXELS,
  SMOOTH_SCROLL,
  INSTANT_SCROLL,
  REDUCED_MOTION_QUERY,
  IN_ZONE,
  PASSED,
  NOT_REACHED,
  NOT_FOUND_INDEX,
  FIRST_INDEX,
  DIFF_ROW_LIMIT,
  DIFF_FILE_START,
  DIFF_FILE_MARKERS,
  DIFF_HUNK_START,
  DIFF_ADD_MARKER,
  DIFF_REMOVE_MARKER,
  DIFF_NOTE_MARKER,
  DIFF_BINARY_STARTS,
  DIFF_EXTENSION,
  TRAILING_CARRIAGE_RETURN,
  STATUS_DATE_SUFFIX_PATTERN,
  TRAILING_NEWLINES_PATTERN,
  NEUTRAL_STATUS_ICON,
  INFO_STRING_SEPARATOR,
  HEADING_OPENING_PATTERN,
};
