import type { ReviewOutcome } from '@/types/task';

/** "other" is a severity the protocol does not define: shown with the label the file gave it. */
type FindingSeverity = 'important' | 'nit' | 'other';

/** The labelled parts of a finding, and "text" for what the file wrote without a label. */
type FindingPartKind = 'what' | 'why' | 'fix' | 'text';

interface FindingPart {
  kind: FindingPartKind;
  text: string;
}

interface ParsedFinding {
  severity: FindingSeverity;
  /** "Important" or "Nit", or the label as the file wrote it for an undefined severity. */
  severityLabel: string;
  location: string | null;
  /** In the order of the file; markdown source, not yet rendered. */
  parts: FindingPart[];
  /** A defined severity, a location, and exactly What, Why and Fix. */
  isComplete: boolean;
}

interface ParsedReview {
  /** The verdict word of line 1; null when line 1 is not one (the file is invalid, or empty). */
  verdict: ReviewOutcome | null;
  /** The rest of line 1 after the verdict word; the whole line when it holds no verdict. */
  headline: string;
  findings: ParsedFinding[];
  /** Non-blank lines that belong to no finding (sections, summary prose, notes): the file holds them, the overview does not. */
  otherLines: number;
  /** Whether the last non-blank line is the closing line. */
  isClosed: boolean;
}

/** A finding bullet before its text is split into parts. */
interface RawFinding {
  label: string;
  first: string;
  continuation: string[];
}

/** Where a "What:", "Why:" or "Fix:" label starts and where its text begins. */
interface LabelHit {
  index: number;
  end: number;
  kind: FindingPartKind;
}

export type { FindingSeverity, FindingPartKind, FindingPart, ParsedFinding, ParsedReview, RawFinding, LabelHit };
