import { LINE_BREAK, META_KEYS, META_LINE_PATTERN, TITLE_PREFIX } from '@/constants/document';
import type { DocumentHeadParts, MetaEntry } from '@/types/document';

/** Splits the head of an artifact (verdict line, `# title`, the `Key: value` block) from its body. Line endings must already be `\n`. */
class DocumentHead {
  split(text: string, withVerdict: boolean): DocumentHeadParts {
    const lines = text.split(LINE_BREAK);

    const verdict = withVerdict ? (lines.shift() as string) : null; // split always yields one entry

    let afterTitle = 0;

    let title: string | null = null;

    const titleIndex = this.skipBlank(lines, 0);

    if (lines[titleIndex]?.startsWith(TITLE_PREFIX)) {
      title = lines[titleIndex].slice(TITLE_PREFIX.length).trim() || null;

      afterTitle = titleIndex + 1;
    }

    // a block counts only right after a title or a verdict line; elsewhere a `Key: value` line is prose
    const { meta, end } = title !== null || withVerdict ? this.readMeta(lines, this.skipBlank(lines, afterTitle)) : { meta: [], end: 0 };

    return { verdict, title, meta, body: lines.slice(meta.length > 0 ? end : afterTitle).join(LINE_BREAK) };
  }

  /** A block counts only when a blank line or the end of the file follows it: otherwise it is the start of a paragraph. */
  private readMeta(lines: string[], start: number): { meta: MetaEntry[]; end: number } {
    const meta: MetaEntry[] = [];

    let end = start;

    for (let match = this.entryOf(lines[end]); match !== null; match = this.entryOf(lines[end])) {
      meta.push(match);

      end += 1;
    }

    return end < lines.length && lines[end].trim() !== '' ? { meta: [], end: start } : { meta, end };
  }

  private entryOf(line: string | undefined): MetaEntry | null {
    const match = META_LINE_PATTERN.exec(line?.trimEnd() ?? '');

    return match !== null && META_KEYS.includes(match[1]) ? { key: match[1], value: match[2] } : null;
  }

  private skipBlank(lines: string[], from: number): number {
    let index = from;

    while (index < lines.length && lines[index].trim() === '') {
      index += 1;
    }

    return index;
  }
}

export default DocumentHead;
