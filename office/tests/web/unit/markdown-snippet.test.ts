// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import sampleMarkdownRenderer from '../sample-markdown-renderer';

const renderer = sampleMarkdownRenderer();

describe('renderSnippet: the text of a finding or a note on the overview', () => {
  it('renders one line inline and several lines as blocks, with links opening in a new tab', () => {
    expect(renderer.renderSnippet('a **b** `c` [d](https://example.test)')).toBe('a <strong>b</strong> <code>c</code> <a href="https://example.test" target="_blank" rel="noopener noreferrer">d</a>');

    const html = renderer.renderSnippet('first\n\n- one\n- two\n\n```\ncode\n```');

    expect(html).toContain('<p>first</p>');

    expect(html).toContain('<li>one</li>');

    expect(html).toContain('<pre><code>code\n</code></pre>');
  });

  it('never carries a heading, an id, a name or a style, so the page keeps one h1 and unique ids', () => {
    const html = renderer.renderSnippet('# Title\n\n## Sub\n\ntext\n\n<h1 id="round-listbox" style="color:red">raw</h1>\n\n<a name="top" id="x">anchor</a>\n\n- ### in a list\n\n> ### in a quote');

    expect(html).not.toMatch(/<h[1-6]/);

    expect(html).not.toMatch(/\b(id|name|style)=/);

    expect(html).toContain('<strong>Title</strong>');

    expect(html).toContain('<strong>Sub</strong>');

    expect(html).toContain('raw');

    expect(html).toContain('in a list');

    expect(html).toContain('in a quote');

    expect(renderer.renderSnippet('a <h1 id="x">inline</h1> b')).not.toMatch(/<h1|id=/);
  });

  it('strips script, handlers and javascript links, in one line and in blocks', () => {
    for (const markdown of ['<script>alert(1)</script> <img src=x onerror=alert(2)> [x](javascript:alert(3))', 'para\n\n<script>alert(1)</script>\n\n<img src=x onerror=alert(2)>\n\n[x](javascript:alert(3))']) {
      const html = renderer.renderSnippet(markdown);

      expect(html).not.toContain('<script');

      expect(html).not.toContain('onerror');

      expect(html).not.toContain('javascript:');
    }
  });
});
