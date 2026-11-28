import DOMPurify from 'dompurify';
import { JSDOM } from 'jsdom';
import { marked } from 'marked';
import addLinkHook from '@/board/link-hook';
import MarkdownRenderer from '@/board/markdown-renderer';

/**
 * A real renderer wired like src/main.ts. The sanitizer runs on a jsdom window whatever environment the test
 * runs in: happy-dom's parser drops the first node of the html DOMPurify parses, which a browser does not.
 */
function sampleMarkdownRenderer(): MarkdownRenderer {
  const purify = DOMPurify(new JSDOM('').window as unknown as Parameters<typeof DOMPurify>[0]);

  addLinkHook(purify);

  return new MarkdownRenderer(purify, marked);
}

export default sampleMarkdownRenderer;
