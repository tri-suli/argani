import type { RowTone } from '@/types/file-tree';
import type { FindingPartKind, FindingSeverity, ParsedReview } from '@/types/review-file';
import type { ReviewState, TaskDetail, TaskFile } from '@/types/task';

/** Which findings the chips of the overview show. */
type FindingFilter = 'all' | 'important' | 'nit';

/** The sanitized markdown renderer the overview draws the texts of the findings with. */
interface TextRenderer {
  renderSnippet(markdown: string): string;
}

/** What a verdict looks like: the word, the icon, the tone, and the same in words for screen readers. */
interface RoundStatus {
  label: string;
  icon: string;
  tone: RowTone;
  spinning: boolean;
  toneLabel: string;
}

/** One row of the Round dropdown. */
interface RoundOption {
  round: number;
  title: string;
  status: RoundStatus;
}

interface ReviewerCard {
  key: string;
  /** The checklist name, or "human". */
  name: string;
  isHuman: boolean;
  status: RoundStatus;
  /** The file of the reviewer, to open in the reader; null while it does not exist. */
  path: string | null;
  headline: string;
  /** "2 important · 5 nits"; empty while the reviewer has not reported or its file could not be read. */
  counts: string;
  /** The model the task detail names for this reviewer; null when it names none (or "inherit"). */
  model: string | null;
  /** Says that the file holds text that is not a finding (shown as notes); empty when it holds nothing else. */
  otherNote: string;
  /** The reviewer has not reported yet. */
  isPending: boolean;
}

interface FindingPartView {
  kind: FindingPartKind;
  /** "What", "Why", "Fix"; empty for text the file wrote without a label. */
  label: string;
  /** Sanitized html. */
  html: string;
  isLabelled: boolean;
  isFix: boolean;
}

interface FindingView {
  key: string;
  severity: FindingSeverity;
  severityLabel: string;
  icon: string;
  location: string | null;
  reviewer: string;
  isHuman: boolean;
  parts: FindingPartView[];
}

type FindingCounts = Record<FindingFilter, number>;

interface FilterChip {
  filter: FindingFilter;
  label: string;
  count: number;
}

/** Everything the summary sentence of a round is made of. */
/** What a reviewer wrote besides its findings and verdict, shown under the findings. */
interface ReviewerNotes {
  key: string;
  reviewer: string;
  isHuman: boolean;
  title: string;
  /** Sanitized html. */
  html: string;
}

interface RoundTally {
  /** Reviewers (the human included) whose file holds notes. */
  notes: number;
  /** Reviewer files expected or present, the human's not counted. */
  seats: number;
  passed: number;
  changes: number;
  pending: number;
  invalid: number;
  /** Files that exist but could not be fetched. */
  unreadable: number;
  /** Files that were read and are no longer pending, the human's included. */
  read: number;
  hasHuman: boolean;
  important: number;
  nits: number;
  other: number;
}

interface RoundView {
  round: number;
  title: string;
  status: RoundStatus;
  summary: string;
  cards: ReviewerCard[];
  /** Important first, then nits, then the rest; stable within a severity. */
  findings: FindingView[];
  notes: ReviewerNotes[];
  counts: FindingCounts;
}

/** The input of `RoundOverview.build`. */
interface BuildInput {
  detail: TaskDetail;
  round: number;
  /** The text of each review file of the round by path; null for a file that could not be read. */
  texts: Record<string, string | null>;
}

/** What is known of one reviewer of a round before it becomes a card. */
interface Seat {
  name: string;
  file: TaskFile | undefined;
  parsed: ParsedReview | null;
  state: ReviewState;
}

export type { FindingFilter, TextRenderer, RoundStatus, RoundOption, ReviewerCard, ReviewerNotes, FindingPartView, FindingView, FindingCounts, FilterChip, RoundTally, RoundView, BuildInput, Seat };
