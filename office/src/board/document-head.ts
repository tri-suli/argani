import { LINE_BREAK, META_LINE_PATTERN, TITLE_PREFIX } from '@/constants/document';
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

    const metaStart = this.skipBlank(lines, afterTitle);

    const { meta, end } = this.readMeta(lines, metaStart);

    return { verdict, title, meta, body: lines.slice(meta.length > 0 ? end : afterTitle).join(LINE_BREAK) };
  }

  /** A block counts only when a blank line or the end of the file follows it: otherwise it is the start of a paragraph. */
  private readMeta(lines: string[], start: number): { meta: MetaEntry[]; end: number } {
    const meta: MetaEntry[] = [];

    let end = start;

    for (let match = META_LINE_PATTERN.exec(lines[end]?.trimEnd() ?? ''); match !== null; match = META_LINE_PATTERN.exec(lines[end]?.trimEnd() ?? '')) {
      meta.push({ key: match[1], value: match[2] });

      end += 1;
    }

    return end < lines.length && lines[end].trim() !== '' ? { meta: [], end: start } : { meta, end };
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
