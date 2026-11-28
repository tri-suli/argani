import {
  BACKTICK, BLOCK_START, BYTE_ORDER_MARK, CLOSING_LINE, CODE_SPAN_WRAPPER, FENCE_CLOSING, FENCE_OPENING, FINDING_START, FULL_PART_COUNT, INDENTED_LINE, LABEL_KINDS, LEADING_WHITESPACE, LINE_BREAK, LINE_ENDINGS, LOCATION_BEFORE_DASH, NOT_FOUND,
  PART_LABEL, PART_TEXT, SEVERITIES, SEVERITY_OTHER, SEVERITY_LABELS, VERDICT_LINE, VERDICT_WORDS, WHITESPACE,
} from '@/constants/review-file';
import type { FindingPart, LabelHit, OpenFence, ParsedFinding, ParsedReview, RawFinding } from '@/types/review-file';

/**
 * Reads a review file the way plugins/argani/docs/review-protocol.md defines it: line 1 is the verdict (hooks and
 * factory_state.py read its first word), the findings are bullets "- [Important|Nit] file:line - What: ... Why: ... Fix: ...",
 * the last line is the closing line. A bullet that departs from that is still a finding, with whatever was recognised.
 */
class ReviewParser {
  parse(text: string): ParsedReview {
    const lines = text.replace(BYTE_ORDER_MARK, '').replace(LINE_ENDINGS, LINE_BREAK).split(LINE_BREAK);

    while (lines.length > 0 && lines[lines.length - 1].trim() === '') {
      lines.pop();
    }

    const isClosed = lines.length > 0 && lines[lines.length - 1].trim() === CLOSING_LINE;

    if (isClosed) {
      lines.pop();
    }

    const [first = '', ...body] = lines;

    const { blocks, notes } = this.collect(body);

    return { ...this.verdictOf(first), findings: blocks.map((block) => this.toFinding(block)), notes, isClosed };
  }

  private verdictOf(line: string): Pick<ParsedReview, 'verdict' | 'headline'> {
    const [, word = '', rest = ''] = VERDICT_LINE.exec(line.trim()) ?? [];

    return Object.hasOwn(VERDICT_WORDS, word) ? { verdict: VERDICT_WORDS[word], headline: rest.trim() } : { verdict: null, headline: line.trim() };
  }

  /**
   * The finding bullets with the lines that continue them (indented lines, and, as in markdown, lines that follow
   * directly without a blank line; a fenced block stays whole), and everything else as notes, in order.
   */
  private collect(body: string[]): { blocks: RawFinding[]; notes: string } {
    const blocks: RawFinding[] = [];

    const notes: string[] = [];

    let current: RawFinding | null = null;

    let fence: OpenFence | null = null;

    let blanks = 0;

    let afterFinding = false;

    for (const line of body) {
      if (fence !== null) {
        (fence.inFinding ? (current as RawFinding).continuation : notes).push(line);

        fence = this.closes(fence, line) ? null : fence;

        continue;
      }

      const start = FINDING_START.exec(line);

      if (start !== null) {
        current = { label: start[1], first: start[2], continuation: [] };

        blocks.push(current);

        blanks = 0;

        afterFinding = true;
      } else if (line.trim() === '') {
        blanks += 1;
      } else if (current !== null && (INDENTED_LINE.test(line) || (blanks === 0 && !BLOCK_START.test(line)))) {
        current.continuation.push(...Array<string>(blanks).fill(''), line);

        blanks = 0;

        fence = this.opening(line, true);
      } else {
        current = null;

        if (notes.length > 0 && (blanks > 0 || afterFinding) && notes[notes.length - 1] !== '') {
          notes.push('');
        }

        notes.push(line);

        blanks = 0;

        afterFinding = false;

        fence = this.opening(line, false);
      }
    }

    return { blocks, notes: notes.join(LINE_BREAK).trim() };
  }

  private opening(line: string, inFinding: boolean): OpenFence | null {
    const match = FENCE_OPENING.exec(line);

    return match === null ? null : { marker: match[1][0], length: match[1].length, inFinding };
  }

  private closes(fence: OpenFence, line: string): boolean {
    const match = FENCE_CLOSING.exec(line);

    return match !== null && match[1][0] === fence.marker && match[1].length >= fence.length;
  }

  private toFinding(raw: RawFinding): ParsedFinding {
    const text = [raw.first, ...this.dedented(raw.continuation)].join(LINE_BREAK).trim();

    const hits = this.labelHits(text);

    const prefix = (hits.length === 0 ? text : text.slice(0, hits[0].index)).trim();

    const located = hits.length === 0 ? null : LOCATION_BEFORE_DASH.exec(prefix);

    const parts: FindingPart[] = [];

    if (located === null && prefix !== '') {
      parts.push({ kind: PART_TEXT, text: prefix });
    }

    hits.forEach((hit, position) => {
      const labelled = text.slice(hit.end, hits[position + 1]?.index ?? text.length).trim();

      if (labelled !== '') {
        parts.push({ kind: hit.kind, text: labelled });
      }
    });

    const label = raw.label.trim().toLowerCase();

    const known = Object.hasOwn(SEVERITIES, label) ? SEVERITIES[label] : undefined;

    const location = located === null ? null : located[1].replace(CODE_SPAN_WRAPPER, '$1');

    return {
      severity: known ?? SEVERITY_OTHER,
      severityLabel: known === undefined ? raw.label.trim() : SEVERITY_LABELS[known],
      location,
      parts,
      isComplete: known !== undefined && location !== null && parts.length === FULL_PART_COUNT && parts.every((part) => part.kind !== PART_TEXT),
    };
  }

  /** The continuation lines without the indentation they all share, so a nested list is a list and not a code block. */
  private dedented(lines: string[]): string[] {
    const indents = lines.filter((line) => line.trim() !== '').map((line) => (LEADING_WHITESPACE.exec(line) as RegExpExecArray)[0].length);

    const shared = Math.min(...indents);

    return lines.map((line) => (line.trim() === '' ? '' : line.slice(shared)));
  }

  /** The first What, Why and Fix label of the text, outside code spans and not glued to the word before. */
  private labelHits(text: string): LabelHit[] {
    const hits: LabelHit[] = [];

    let index = 0;

    while (index < text.length) {
      if (text[index] === BACKTICK) {
        index = this.afterCodeSpan(text, index);

        continue;
      }

      PART_LABEL.lastIndex = index;

      const match = (index === 0 || WHITESPACE.test(text[index - 1])) ? PART_LABEL.exec(text) : null;

      if (match !== null && !hits.some((hit) => hit.kind === LABEL_KINDS[match[1]])) {
        hits.push({ index, end: index + match[0].length, kind: LABEL_KINDS[match[1]] });
      }

      index += match === null ? 1 : match[0].length;
    }

    return hits;
  }

  /** Where scanning goes on after the backticks at `start`: past the span they open, or just past an unmatched run. */
  private afterCodeSpan(text: string, start: number): number {
    let runEnd = start;

    while (text[runEnd] === BACKTICK) {
      runEnd += 1;
    }

    const length = runEnd - start;

    let cursor = text.indexOf(BACKTICK, runEnd);

    while (cursor !== NOT_FOUND) {
      let closeEnd = cursor;

      while (text[closeEnd] === BACKTICK) {
        closeEnd += 1;
      }

      if (closeEnd - cursor === length) {
        return closeEnd;
      }

      cursor = text.indexOf(BACKTICK, closeEnd);
    }

    return runEnd;
  }
}

export default ReviewParser;
