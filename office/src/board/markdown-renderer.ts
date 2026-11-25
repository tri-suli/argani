import { NOT_FOUND_INDEX, SANITIZE_OPTIONS, SECTION_HEADING_PREFIX, SUMMARY_HEADING } from '@/constants/markdown';
import type { MarkdownParser, MarkdownSanitizer } from '@/types/markdown';
import type { FileTone } from '@/types/task';
import type { RenderedDocument } from '@/types/view';

/** Artifacts are untrusted text: every rendered string goes through the sanitizer before it reaches x-html. */
class MarkdownRenderer {
  constructor(
    private readonly sanitizer: MarkdownSanitizer,
    private readonly parser: MarkdownParser,
  ) {}

  renderMarkdown(markdown: string): string {
    return this.sanitizer.sanitize(this.parser.parse(markdown, { async: false }), SANITIZE_OPTIONS);
  }

  renderDocument(text: string, tone: FileTone | null): RenderedDocument {
    const lines = text.split('\n');

    const verdict = tone === null ? null : lines.shift() as string; // split always yields one entry

    const start = lines.findIndex((line) => line.trim() === SUMMARY_HEADING);

    let summaryHtml: string | null = null;

    if (start !== NOT_FOUND_INDEX) {
      const next = lines.findIndex((line, index) => index > start && line.startsWith(SECTION_HEADING_PREFIX));

      const end = next === NOT_FOUND_INDEX ? lines.length : next;

      summaryHtml = this.renderMarkdown(lines.slice(start + 1, end).join('\n'));

      lines.splice(start, end - start);
    }

    return { verdict, tone, summaryHtml, bodyHtml: this.renderMarkdown(lines.join('\n')) };
  }
}

export default MarkdownRenderer;
