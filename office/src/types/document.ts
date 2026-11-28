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
  icon: string;
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
  /** The box is ticked: `[x]`. */
  checked: boolean;
}

interface CriterionView {
  id: string;
  claimHtml: string;
  verifyHtml: string;
  manual: boolean;
  checked: boolean;
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
  /** The `diff ` line that begins a file of the diff. */
  fileStart: boolean;
}

interface DiffView {
  rows: DiffRow[];
  total: number;
  truncated: boolean;
}

/** Where a heading is in relation to the reading zone near the top of the viewport. */
type SectionPosition = 'zone' | 'above' | 'below';

interface SectionObserver {
  observe(element: Element): void;
  disconnect(): void;
}

interface ReaderEnvironment {
  /** `onChange` runs when a heading enters or leaves the reading zone. */
  createObserver(onChange: () => void): SectionObserver;
  findElement(id: string): HTMLElement | null;
  /** Read from the element's place on the screen, since an observer says nothing about a heading that jumps from one side of the zone to the other. */
  positionOf(id: string): SectionPosition;
  /** Runs `onScroll` at most once per frame while the page scrolls and `onSettled` once it has stopped; returns the function that stops listening. */
  watchScroll(handlers: { onScroll: () => void; onSettled: () => void }): () => void;
  /** The page cannot scroll any further down. */
  isAtPageEnd(): boolean;
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
  /** The reader scrolled: works out which section is in view. */
  change(): void;
  /** The scrolling stopped: a click-scroll the reader interrupted lets go of its section. */
  settle(): void;
}

export type { MetaEntry, DocumentHeadParts, DocumentStatus, OutlineEntry, ParsedCriterion, CriterionView, HtmlBlock, CodeBlock, CriteriaBlock, DocumentBlock, DiffRowKind, DiffRow, DiffView, SectionPosition, SectionObserver, ReaderEnvironment, OutlineTracker };
