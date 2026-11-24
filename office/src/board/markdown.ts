import DOMPurify from 'dompurify';
import { marked } from 'marked';
import type { FileTone } from './types';

export interface RenderedDocument {
  /** First line of the file, shown as a badge, when the file has a tone. */
  verdict: string | null;
  tone: FileTone | null;
  /** The `## Summary` section, if any. */
  summaryHtml: string | null;
  bodyHtml: string;
}

// Artifacts are untrusted text: every rendered string goes through DOMPurify before it reaches x-html.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.hasAttribute('href')) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

// Documents are read-only text: no form controls, images, embeds or styles; Alpine-looking attributes
// (x-*, @*, :*) are not in DOMPurify's allow list and so never survive.
const SANITIZE_OPTIONS = {
  FORBID_TAGS: ['form', 'input', 'button', 'select', 'textarea', 'img', 'style', 'iframe', 'object', 'embed'],
  FORBID_ATTR: ['style'],
};

export function renderMarkdown(markdown: string): string {
  return DOMPurify.sanitize(marked.parse(markdown, { async: false }), SANITIZE_OPTIONS);
}

const SUMMARY_HEADING = '## Summary';

export function renderDocument(text: string, tone: FileTone | null): RenderedDocument {
  const lines = text.split('\n');
  const verdict = tone === null ? null : lines.shift() as string // split always yields one entry;
  const start = lines.findIndex((line) => line.trim() === SUMMARY_HEADING);
  let summaryHtml: string | null = null;
  if (start !== -1) {
    const next = lines.findIndex((line, index) => index > start && line.startsWith('## '));
    const end = next === -1 ? lines.length : next;
    summaryHtml = renderMarkdown(lines.slice(start + 1, end).join('\n'));
    lines.splice(start, end - start);
  }
  return { verdict, tone, summaryHtml, bodyHtml: renderMarkdown(lines.join('\n')) };
}
