// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { renderDocument, renderMarkdown } from '../../../src/board/markdown';

describe('renderMarkdown', () => {
  it('renders markdown to html', () => {
    expect(renderMarkdown('# Title\n\n**bold**')).toContain('<h1>Title</h1>');
  });

  it('strips script elements and event handlers', () => {
    const html = renderMarkdown('<script>alert(1)</script>\n\n<img src=x onerror="alert(2)">\n\n[x](javascript:alert(3))');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('javascript:');
  });

  it('opens links in a new tab safely and leaves other elements alone', () => {
    const html = renderMarkdown('[docs](https://example.test) and `code`');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(renderMarkdown('<a name="anchor">x</a>')).not.toContain('target');
  });
});

describe('renderDocument', () => {
  it('shows the first line as verdict when the file has a tone', () => {
    const document = renderDocument('PASS ok\n\nbody', 'good');
    expect(document).toMatchObject({ verdict: 'PASS ok', tone: 'good', summaryHtml: null });
    expect(document.bodyHtml).toContain('<p>body</p>');
    expect(document.bodyHtml).not.toContain('PASS ok');
  });

  it('keeps the first line when there is no tone', () => {
    const document = renderDocument('# Spec', null);
    expect(document.verdict).toBeNull();
    expect(document.bodyHtml).toContain('<h1>Spec</h1>');
  });

  it('moves the Summary section out of the body, up to the next heading', () => {
    const document = renderDocument('# T\n\n## Summary\n- one\n\n## Details\nmore', null);
    expect(document.summaryHtml).toContain('<li>one</li>');
    expect(document.bodyHtml).toContain('Details');
    expect(document.bodyHtml).not.toContain('one');
  });

  it('takes a Summary section that runs to the end', () => {
    const document = renderDocument('## Summary\nlast words', null);
    expect(document.summaryHtml).toContain('last words');
    expect(document.bodyHtml).toBe('');
  });

  it('survives an empty tone-bearing file', () => {
    expect(renderDocument('', 'warn')).toMatchObject({ verdict: '', summaryHtml: null });
  });
});

describe('sanitizer hardening', () => {
  it.each(['form', 'input', 'button', 'select', 'textarea', 'img', 'style', 'iframe', 'object', 'embed'])(
    'removes <%s>', (tag) => {
      const html = renderMarkdown(`before <${tag} src="https://evil.test/x">inner</${tag}> after`);
      expect(html).not.toContain(`<${tag}`);
    });

  it('removes the style attribute but keeps the element', () => {
    const html = renderMarkdown('<p style="position:fixed;inset:0">covers the page</p>');
    expect(html).toContain('covers the page');
    expect(html).not.toContain('style');
  });

  it('never keeps Alpine-looking attributes', () => {
    const html = renderMarkdown('<div x-init="alert(1)" x-data="{a:1}" @click="alert(2)" :class="alert(3)" x-html="y" x-on:click="z">text</div>');
    expect(html).toContain('text');
    for (const name of ['x-init', 'x-data', '@click', ':class', 'x-html', 'x-on:click']) {
      expect(html).not.toContain(name);
    }
  });
});
