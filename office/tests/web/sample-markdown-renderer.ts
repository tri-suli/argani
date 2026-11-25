import DOMPurify from 'dompurify';
import { marked } from 'marked';
import addLinkHook from '@/board/link-hook';
import MarkdownRenderer from '@/board/markdown-renderer';

/** A real renderer wired like src/main.ts, for tests that run in a DOM environment. */
function sampleMarkdownRenderer(): MarkdownRenderer {
  const purify = DOMPurify(window);

  addLinkHook(purify);

  return new MarkdownRenderer(purify, marked);
}

export default sampleMarkdownRenderer;
