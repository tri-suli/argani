import type { FileTone } from '@/types/task';

/** One `Key: value` line of the block that follows the title of an artifact. */
interface MetaEntry {
  key: string;
  value: string;
}

interface DocumentHeadParts {
  /** The first line, when the file has a verdict line. */
  verdict: string | null;
  /** The text of the leading `# ` heading, when the document starts with one. */
  title: string | null;
  meta: MetaEntry[];
  body: string;
}

/** The pill of the document head. */
interface DocumentStatus {
  label: string;
  tone: FileTone | null;
}

interface OutlineEntry {
  id: string;
  label: string;
  /** 1 for a section, 2 for a subsection. */
  level: number;
  /** How many items the section holds, for the acceptance criteria; null for the others. */
  count: number | null;
}

/** An acceptance criterion in the shape `n. [ ] <claim> — verify: <how>` (templates/intent.md). */
interface ParsedCriterion {
  number: number;
  claim: string;
  verify: string;
  /** The verification is `manual: <step>`: only a human can check it. */
  manual: boolean;
}

interface CriterionView {
  id: string;
  claimHtml: string;
  verifyHtml: string;
  manual: boolean;
}

interface HtmlBlock {
  kind: 'html';
  key: string;
  html: string;
}

interface CodeBlock {
  kind: 'code';
  key: string;
  language: string;
  text: string;
}

interface CriteriaBlock {
  kind: 'criteria';
  key: string;
  criteria: CriterionView[];
}

type DocumentBlock = HtmlBlock | CodeBlock | CriteriaBlock;

type DiffRowKind = 'file' | 'hunk' | 'add' | 'remove' | 'context' | 'note' | 'binary';

interface DiffRow {
  key: number;
  kind: DiffRowKind;
  text: string;
}

interface DiffView {
  rows: DiffRow[];
  total: number;
  truncated: boolean;
}

/** What the outline needs to know about a section heading scrolling through the reading zone. */
interface SectionVisibility {
  id: string;
  intersecting: boolean;
  /** It left the zone through the bottom: the reader scrolled back above the heading. */
  below: boolean;
}

interface SectionObserver {
  observe(element: Element): void;
  disconnect(): void;
}

interface ReaderEnvironment {
  createObserver(onChange: (entries: SectionVisibility[]) => void): SectionObserver;
  findElement(id: string): HTMLElement | null;
  prefersReducedMotion(): boolean;
}

interface OutlineTracker {
  /** The section in view, highlighted in the outline. */
  activeId: string | null;
  /** Observes the headings of these ids once they are in the page. */
  track(ids: string[]): void;
  stop(): void;
  scrollTo(id: string): void;
  /** A click on an in-document link of the markdown scrolls to its heading instead of changing the route. */
  followAnchor(event: Event): void;
}

export type { MetaEntry, DocumentHeadParts, DocumentStatus, OutlineEntry, ParsedCriterion, CriterionView, HtmlBlock, CodeBlock, CriteriaBlock, DocumentBlock, DiffRowKind, DiffRow, DiffView, SectionVisibility, SectionObserver, ReaderEnvironment, OutlineTracker };
