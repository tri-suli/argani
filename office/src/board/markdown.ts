import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { ANCHOR_TAG_NAME, HREF_ATTRIBUTE, NOT_FOUND_INDEX, SANITIZE_OPTIONS, SECTION_HEADING_PREFIX, SUMMARY_HEADING } from '@/board/constants';
import type { FileTone, RenderedDocument } from '@/board/types';

// Artifacts are untrusted text: every rendered string goes through DOMPurify before it reaches x-html.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === ANCHOR_TAG_NAME && node.hasAttribute(HREF_ATTRIBUTE)) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

function renderMarkdown(markdown: string): string {
  return DOMPurify.sanitize(marked.parse(markdown, { async: false }), SANITIZE_OPTIONS);
}

function renderDocument(text: string, tone: FileTone | null): RenderedDocument {
  const lines = text.split('\n');
  const verdict = tone === null ? null : lines.shift() as string; // split always yields one entry
  const start = lines.findIndex((line) => line.trim() === SUMMARY_HEADING);
  let summaryHtml: string | null = null;
  if (start !== NOT_FOUND_INDEX) {
    const next = lines.findIndex((line, index) => index > start && line.startsWith(SECTION_HEADING_PREFIX));
    const end = next === NOT_FOUND_INDEX ? lines.length : next;
    summaryHtml = renderMarkdown(lines.slice(start + 1, end).join('\n'));
    lines.splice(start, end - start);
  }
  return { verdict, tone, summaryHtml, bodyHtml: renderMarkdown(lines.join('\n')) };
}

export { renderMarkdown, renderDocument };
