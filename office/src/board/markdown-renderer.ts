import type { Token, Tokens } from 'marked';
import AcceptanceCriteria from '@/board/acceptance-criteria';
import DocumentHead from '@/board/document-head';
import HeadingIds from '@/board/heading-ids';
import readingStats from '@/board/reading-time';
import tokenText from '@/board/token-text';
import {
  ACCEPTANCE_CRITERIA_TITLE, APPROVED_STATUS_PREFIX, CRITERION_ID_PREFIX, HEADING_OPENING_PATTERN, INFO_STRING_SEPARATOR, LINE_BREAK, MAX_HEADING_DEPTH,
  MAX_OUTLINE_DEPTH, NEUTRAL_STATUS_ICON, NEWLINE_PATTERN, RAW_HEADING_TAG_PATTERN, TOKEN_CODE, TOKEN_HEADING, TOKEN_HTML, TOKEN_LIST, SECTION_DEPTH, STATUS_DATE_SUFFIX_PATTERN, STATUS_KEY, SUMMARY_TITLE, TRAILING_NEWLINES_PATTERN,
} from '@/constants/document';
import { FILE_TONE_ICONS } from '@/constants/file-tree';
import { SANITIZE_OPTIONS } from '@/constants/markdown';
import type { CriterionView, DocumentBlock, DocumentStatus, MetaEntry, OutlineEntry } from '@/types/document';
import type { MarkdownParser, MarkdownSanitizer } from '@/types/markdown';
import type { FileTone } from '@/types/task';
import type { RenderedDocument } from '@/types/view';

/** What one document has gathered while its tokens are walked. */
interface Assembly {
  ids: HeadingIds;
  blocks: DocumentBlock[];
  outline: OutlineEntry[];
  /** Tokens waiting to become one html block. */
  pending: Token[];
  /** The tokens of the Summary section while it is being read; null before and after it. */
  summary: Token[] | null;
  summaryHtml: string | null;
  summaryId: string | null;
  /** The outline entry of the Acceptance criteria section while it is being read. */
  criteria: OutlineEntry | null;
}

/** Artifacts are untrusted text: every rendered string goes through the sanitizer before it reaches x-html. */
class MarkdownRenderer {
  constructor(
    private readonly sanitizer: MarkdownSanitizer,
    private readonly parser: MarkdownParser,
    private readonly documentHead: DocumentHead = new DocumentHead(),
    private readonly acceptanceCriteria: AcceptanceCriteria = new AcceptanceCriteria(),
  ) {}

  renderMarkdown(markdown: string): string {
    return this.sanitizer.sanitize(this.parser.parse(markdown, { async: false }), SANITIZE_OPTIONS);
  }

  renderDocument(text: string, tone: FileTone | null): RenderedDocument {
    const normalized = text.replace(NEWLINE_PATTERN, LINE_BREAK);

    const parts = this.documentHead.split(normalized, tone !== null);

    const assembly: Assembly = { ids: new HeadingIds(), blocks: [], outline: [], pending: [], summary: null, summaryHtml: null, summaryId: null, criteria: null };

    for (const token of this.parser.lexer(parts.body)) {
      this.add(assembly, token);
    }

    this.closeSummary(assembly);

    this.flush(assembly);

    const { words, minutes } = readingStats(normalized);

    return {
      status: this.statusOf(parts.meta, parts.verdict, tone),
      titleHtml: parts.title === null ? null : this.renderInline(parts.title),
      meta: parts.meta,
      summaryHtml: assembly.summaryHtml,
      summaryId: assembly.summaryId,
      blocks: assembly.blocks,
      outline: assembly.outline,
      wordCount: words,
      readMinutes: minutes,
    };
  }

  private renderInline(markdown: string): string {
    return this.sanitizer.sanitize(this.parser.parseInline(markdown, { async: false }), SANITIZE_OPTIONS);
  }

  private renderTokens(tokens: Token[]): string {
    return this.sanitizer.sanitize(this.parser.parser(tokens), SANITIZE_OPTIONS);
  }

  private statusOf(meta: MetaEntry[], verdict: string | null, tone: FileTone | null): DocumentStatus | null {
    const status = meta.find((entry) => entry.key === STATUS_KEY);

    if (status !== undefined) {
      return this.statusPill(status.value.replace(STATUS_DATE_SUFFIX_PATTERN, ''), status.value.startsWith(APPROVED_STATUS_PREFIX) ? 'good' : null);
    }

    return verdict === null ? null : this.statusPill(verdict, tone);
  }

  private statusPill(label: string, tone: FileTone | null): DocumentStatus {
    return { label, tone, icon: tone === null ? NEUTRAL_STATUS_ICON : FILE_TONE_ICONS[tone] };
  }

  private add(assembly: Assembly, token: Token): void {
    if (token.type === TOKEN_HEADING) {
      this.addHeading(assembly, token as Tokens.Heading);

      return;
    }

    const shifted = this.shiftNestedHeadings(token);

    if (assembly.summary !== null) {
      assembly.summary.push(shifted);
    } else if (shifted.type === TOKEN_CODE) {
      this.addCode(assembly, shifted as Tokens.Code);
    } else if (shifted.type === TOKEN_LIST && assembly.criteria !== null) {
      this.addCriteria(assembly, shifted as Tokens.List, assembly.criteria);
    } else {
      assembly.pending.push(shifted);
    }
  }

  /** The page has one h1 (the task title): a heading inside a quote or a list item, or an html heading, moves down a level like the others. */
  private shiftNestedHeadings(token: Token): Token {
    if (token.type === TOKEN_HEADING) {
      return { ...token, depth: Math.min((token as Tokens.Heading).depth + 1, MAX_HEADING_DEPTH) } as Token;
    }

    if (token.type === TOKEN_HTML) {
      return { ...token, text: this.shiftedHtml((token as Tokens.HTML).text) } as Token;
    }

    if ('items' in token) {
      return { ...token, items: (token.items as Token[]).map((item) => this.shiftNestedHeadings(item)) } as Token;
    }

    return 'tokens' in token && token.tokens ? ({ ...token, tokens: token.tokens.map((child) => this.shiftNestedHeadings(child)) } as Token) : token;
  }

  private shiftedHtml(html: string): string {
    return html.replace(RAW_HEADING_TAG_PATTERN, (_tag, slash: string, level: string) => `<${slash}h${Math.min(Number(level) + 1, MAX_HEADING_DEPTH)}`);
  }

  private addHeading(assembly: Assembly, heading: Tokens.Heading): void {
    const label = tokenText(heading.tokens);

    if (heading.depth <= SECTION_DEPTH) {
      this.closeSummary(assembly);

      assembly.criteria = null;
    }

    const isSummary = heading.depth === SECTION_DEPTH && label === SUMMARY_TITLE && assembly.summaryId === null;

    const id = assembly.ids.next(label);

    if (heading.depth <= MAX_OUTLINE_DEPTH) {
      const entry: OutlineEntry = { id, label, level: heading.depth <= SECTION_DEPTH ? 1 : 2, count: null };

      assembly.outline.push(entry);

      if (heading.depth === SECTION_DEPTH && label === ACCEPTANCE_CRITERIA_TITLE) {
        entry.count = 0;

        assembly.criteria = entry;
      }
    }

    if (isSummary) {
      assembly.summary = [];

      assembly.summaryId = id;

      return;
    }

    (assembly.summary ?? assembly.pending).push(this.demoted(heading, id));
  }

  /** The heading one level down (the title is the page's only h1 and the reader's heading the h2), with its id. */
  private demoted(heading: Tokens.Heading, id: string): Tokens.HTML {
    const depth = Math.min(heading.depth + 1, MAX_HEADING_DEPTH);

    const html = this.parser.parser([{ ...heading, depth }]).replace(HEADING_OPENING_PATTERN, `<h$1 id="${id}">`);

    return { type: 'html', raw: '', text: html, pre: false, block: true };
  }

  private closeSummary(assembly: Assembly): void {
    if (assembly.summary !== null) {
      assembly.summaryHtml = this.renderTokens(assembly.summary);

      assembly.summary = null;
    }
  }

  private addCode(assembly: Assembly, code: Tokens.Code): void {
    this.flush(assembly);

    assembly.blocks.push({ kind: 'code', key: String(assembly.blocks.length), language: (code.lang ?? '').split(INFO_STRING_SEPARATOR)[0], text: code.text.replace(TRAILING_NEWLINES_PATTERN, '') });
  }

  /** Items in the artifact format become cards; the others stay list items, in place. */
  private addCriteria(assembly: Assembly, list: Tokens.List, entry: OutlineEntry): void {
    this.flush(assembly);

    const views = list.items.map((item) => this.parsedCriterion(item));

    entry.count = (entry.count as number) + views.filter((view) => view !== null).length;

    for (let start = 0; start < views.length;) {
      let end = start;

      while (end < views.length && (views[end] === null) === (views[start] === null)) {
        end += 1;
      }

      if (views[start] === null) {
        this.addPlainItems(assembly, list, start, end);
      } else {
        assembly.blocks.push({ kind: 'criteria', key: String(assembly.blocks.length), criteria: views.slice(start, end) as CriterionView[] });
      }

      start = end;
    }
  }

  private parsedCriterion(item: Tokens.ListItem): CriterionView | null {
    const lines = item.raw.trimEnd().split(LINE_BREAK);

    const parsed = lines.length === 1 ? this.acceptanceCriteria.parse(lines[0]) : null; // more lines: content the card would drop

    return parsed === null
      ? null
      : {
          id: CRITERION_ID_PREFIX + parsed.number,
          claimHtml: this.renderInline(parsed.claim),
          verifyHtml: this.renderInline(parsed.verify),
          manual: parsed.manual,
          checked: parsed.checked,
        };
  }

  /** A run of items that are not cards, as the list they were in; an ordered list keeps the numbers of its items. */
  private addPlainItems(assembly: Assembly, list: Tokens.List, start: number, end: number): void {
    const first = list.start === '' ? 1 : list.start;

    assembly.pending.push({ ...list, items: list.items.slice(start, end), start: list.ordered ? first + start : list.start });

    this.flush(assembly);
  }

  private flush(assembly: Assembly): void {
    const html = this.renderTokens(assembly.pending);

    assembly.pending = [];

    if (html.trim() !== '') {
      assembly.blocks.push({ kind: 'html', key: String(assembly.blocks.length), html });
    }
  }
}

export default MarkdownRenderer;
