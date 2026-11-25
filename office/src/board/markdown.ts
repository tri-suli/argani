import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { SANITIZE_OPTIONS, SUMMARY_HEADING } from './constants';
import type { FileTone, RenderedDocument } from './types';

// Artifacts are untrusted text: every rendered string goes through DOMPurify before it reaches x-html.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.hasAttribute('href')) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

export function renderMarkdown(markdown: string): string {
  return DOMPurify.sanitize(marked.parse(markdown, { async: false }), SANITIZE_OPTIONS);
}

export function renderDocument(text: string, tone: FileTone | null): RenderedDocument {
  const lines = text.split('\n');
  const verdict = tone === null ? null : lines.shift() as string; // split always yields one entry
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
