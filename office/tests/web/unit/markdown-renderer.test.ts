// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import sampleMarkdownRenderer from '../sample-markdown-renderer';

const renderer = sampleMarkdownRenderer();

describe('renderMarkdown', () => {
  it('renders markdown to html', () => {
    expect(renderer.renderMarkdown('# Title\n\n**bold**')).toContain('<h1>Title</h1>');
  });

  it('strips script elements and event handlers', () => {
    const html = renderer.renderMarkdown('<script>alert(1)</script>\n\n<img src=x onerror="alert(2)">\n\n[x](javascript:alert(3))');

    expect(html).not.toContain('<script');

    expect(html).not.toContain('onerror');

    expect(html).not.toContain('javascript:');
  });

  it('opens links in a new tab safely and leaves other elements alone', () => {
    const html = renderer.renderMarkdown('[docs](https://example.test) and `code`');

    expect(html).toContain('target="_blank"');

    expect(html).toContain('rel="noopener noreferrer"');

    expect(renderer.renderMarkdown('<a name="anchor">x</a>')).not.toContain('target');
  });
});

const SPEC = [
  '# Spec: Install `src/`',
  '',
  'Intent: install-laravel',
  'Status: approved by argani on 2026-11-26',
  'Date: 2026-11-26',
  '',
  '<!-- a comment that is not read -->',
  '',
  '## Summary',
  '',
  'Install the **skeleton**.',
  '',
  '## Approach',
  '',
  '### Commit order',
  '',
  'Each commit passes.',
  '',
  '```bash',
  'git rebase --exec "npm run check"',
  '```',
  '',
  '## Acceptance criteria',
  '',
  '1. [ ] The stack starts — verify: `docker compose ps`',
  '2. [ ] has no verification',
  '3. [ ] The page renders — verify: manual: open it in a browser',
  '4. [ ] has a nested list — verify: `x`',
  '   - detail',
  '',
  '## Out of scope',
  '',
  '- Nothing.',
].join('\n');

type Rendered = ReturnType<typeof renderer.renderDocument>;

const blocksOf = (rendered: Rendered, kind: string) => rendered.blocks.filter((block) => block.kind === kind);

const htmlOf = (rendered: Rendered) => blocksOf(rendered, 'html').map((block) => (block as { html: string }).html);

describe('renderDocument', () => {
  const document = renderer.renderDocument(SPEC, null);

  it('takes the title as sanitized html, the meta block and the status of the head', () => {
    expect(document.titleHtml).toBe('Spec: Install <code>src/</code>');

    expect(document.meta.map((entry) => entry.key)).toEqual(['Intent', 'Status', 'Date']);

    expect(document.status).toEqual({ label: 'approved by argani', tone: 'good', icon: 'check_circle' });
  });

  it('shows the verdict line as the status when the file has no Status line', () => {
    expect(renderer.renderDocument('PASS ok\n\nbody', 'good').status).toEqual({ label: 'PASS ok', tone: 'good', icon: 'check_circle' });

    expect(renderer.renderDocument('CHANGES x\n\nbody', 'warn').status).toEqual({ label: 'CHANGES x', tone: 'warn', icon: 'error' });

    expect(renderer.renderDocument('PASS ok\nStatus: draft\n\nbody', 'good').status).toEqual({ label: 'draft', tone: null, icon: 'edit_note' });

    expect(renderer.renderDocument('# Plain\n\nbody', null).status).toBeNull();

    expect(renderer.renderDocument('', 'warn').status).toEqual({ label: '', tone: 'warn', icon: 'error' });
  });

  it('leaves the verdict out of the body and keeps the first line when there is no tone', () => {
    expect(JSON.stringify(renderer.renderDocument('PASS ok\n\nbody', 'good').blocks)).not.toContain('PASS ok');

    const plain = renderer.renderDocument('Just a first line\n\nbody', null);

    expect(htmlOf(plain)[0]).toContain('Just a first line');
  });

  it('moves the Summary section out of the body, up to the next section, and gives it an id', () => {
    expect(document.summaryHtml).toContain('<strong>skeleton</strong>');

    expect(document.summaryId).toBe('doc-summary');

    expect(JSON.stringify(document.blocks)).not.toContain('skeleton');

    const tail = renderer.renderDocument('## Summary\nlast words', null);

    expect(tail.summaryHtml).toContain('last words');

    expect(tail.blocks).toEqual([]);

    expect(renderer.renderDocument('## Summary\n\n## Next\ntext', null).summaryHtml).toBe('');
  });

  it('keeps subheadings of the summary inside it', () => {
    const nested = renderer.renderDocument('## Summary\n\n### Why\n\nbecause\n\n## Approach', null);

    expect(nested.summaryHtml).toContain('<h4 id="doc-why">Why</h4>');
  });

  it('extracts only the first Summary, and not a heading inside a code fence', () => {
    const twice = renderer.renderDocument('## Summary\n\none\n\n## Summary\n\ntwo', null);

    expect(twice.summaryHtml).toContain('one');

    expect(JSON.stringify(twice.blocks)).toContain('two');

    const fenced = renderer.renderDocument('```md\n## Summary\n```', null);

    expect(fenced.summaryHtml).toBeNull();

    expect(fenced.outline).toEqual([]);
  });

  it('shifts every heading one level down, keeping their order, and caps at h6', () => {
    const html = htmlOf(renderer.renderDocument('intro\n\n# One\n\n## Two\n\n###### Six', null)).join('');

    expect(html).toContain('<h2 id="doc-one">One</h2>');

    expect(html).toContain('<h3 id="doc-two">Two</h3>');

    expect(html).toContain('<h6 id="doc-six">Six</h6>');

    expect(html).not.toContain('<h1');
  });

  it('never renders a second h1: headings nested in quotes and list items and raw html headings shift down too', () => {
    const rendered = renderer.renderDocument(
      ['intro', '', '> # Quoted', '', '- # Listed', '  text', '', '<h1>Raw</h1>', '', '<H2 class="x">Raw two</H2>', '', 'inline <h1>mid</h1> text', '', '<h6>Six</h6>', '', '## Summary', '', '> # In the summary', '', '<h1>Raw summary</h1>'].join('\n'),
      null,
    );

    const everything = htmlOf(rendered).join('') + rendered.summaryHtml;

    expect(everything).not.toMatch(/<h1/i);

    expect(everything).toContain('<h2>Quoted</h2>');

    expect(everything).toContain('<h2>Listed</h2>');

    expect(everything).toContain('<h2>Raw</h2>');

    expect(everything).toMatch(/<h3 class="x">Raw two<\/h3>/);

    expect(everything).toContain('<h2>mid</h2>');

    expect(everything).toContain('<h6>Six</h6>');

    expect(rendered.summaryHtml).toContain('<h2>In the summary</h2>');

    expect(rendered.summaryHtml).toContain('<h2>Raw summary</h2>');
  });

  it('gives duplicate headings unique ids and a heading without letters a fallback id', () => {
    const outline = renderer.renderDocument('## Notes\n\n## Notes\n\n## Notes 2\n\n## ???\n\n## Fish & `a<b`', null).outline;

    expect(outline.map((entry) => entry.id)).toEqual(['doc-notes', 'doc-notes-2', 'doc-notes-2-2', 'doc-section', 'doc-fish-a-b']);

    expect(outline[4].label).toBe('Fish & a<b');
  });

  it('lists sections and subsections in the outline, not deeper headings, with the number of criteria', () => {
    expect(document.outline).toEqual([
      { id: 'doc-summary', label: 'Summary', level: 1, count: null },
      { id: 'doc-approach', label: 'Approach', level: 1, count: null },
      { id: 'doc-commit-order', label: 'Commit order', level: 2, count: null },
      { id: 'doc-acceptance-criteria', label: 'Acceptance criteria', level: 1, count: 2 },
      { id: 'doc-out-of-scope', label: 'Out of scope', level: 1, count: null },
    ]);

    expect(renderer.renderDocument('## A\n\n#### Deep', null).outline).toHaveLength(1);
  });

  it('renders a fenced block as a code block with its language and exact text, never as html', () => {
    expect(blocksOf(document, 'code')).toEqual([{ kind: 'code', isHtml: false, isCode: true, isCriteria: false, key: expect.any(String), language: 'bash', text: 'git rebase --exec "npm run check"' }]);

    expect(htmlOf(document).join('')).not.toContain('<pre');

    const bare = renderer.renderDocument('```\n<b>x</b>\n```\n\n    indented\n', null);

    expect(blocksOf(bare, 'code')).toMatchObject([{ language: '', text: '<b>x</b>' }, { language: '', text: 'indented' }]);

    expect(renderer.renderDocument('```js title=a.js\nx\n```', null).blocks[0]).toMatchObject({ language: 'js' });
  });

  it('turns the criteria of the Acceptance criteria section into cards, and keeps the others as list items', () => {
    const cards = blocksOf(document, 'criteria') as { criteria: unknown[] }[];

    expect(cards.map((block) => block.criteria)).toEqual([[{ id: 'AC-1', claimHtml: 'The stack starts', verifyHtml: '<code>docker compose ps</code>', manual: false, checked: false }], [
      { id: 'AC-3', claimHtml: 'The page renders', verifyHtml: 'open it in a browser', manual: true, checked: false }]]);

    const lists = htmlOf(document).filter((html) => html.includes('<ol'));

    expect(lists).toHaveLength(2);

    expect(lists[0]).toContain('<ol start="2">');

    expect(lists[0]).toContain('has no verification');

    expect(lists[1]).toContain('<ol start="4">');

    expect(lists[1]).toContain('detail');
  });

  it('keeps criteria cards out of other sections and out of a section that only starts with the name', () => {
    const other = renderer.renderDocument('## Notes\n\n1. [ ] x — verify: y\n\n## Acceptance criteria mapping\n\n1. [ ] x — verify: y', null);

    expect(blocksOf(other, 'criteria')).toEqual([]);

    expect(other.outline.map((entry) => entry.count)).toEqual([null, null]);
  });

  it('counts the criteria cards of the section, not its other list items, subsections included', () => {
    const counted = renderer.renderDocument('## Acceptance criteria\n\n- plain\n\n### More\n\n1. [ ] a — verify: b\n2. [x] c — verify: d\n3. nothing\n\n## Next', null);

    expect(counted.outline[0].count).toBe(2);

    expect(blocksOf(counted, 'criteria')).toMatchObject([{ criteria: [{ checked: false }, { checked: true }] }]);

    expect(htmlOf(counted).join('')).toContain('<ul>');
  });

  it('keeps other blocks of the criteria section as html', () => {
    expect(htmlOf(renderer.renderDocument('## Acceptance criteria\n\nSome words.\n', null)).join('')).toContain('Some words.');
  });

  it('tells the page which template a block takes with booleans, so it never compares the kind to a string', () => {
    expect(document.blocks.map((block) => [block.kind, block.isHtml, block.isCode, block.isCriteria])).toEqual(
      document.blocks.map((block) => [block.kind, block.kind === 'html', block.kind === 'code', block.kind === 'criteria']),
    );

    expect(new Set(document.blocks.map((block) => block.kind))).toEqual(new Set(['html', 'code', 'criteria']));
  });

  it('keeps every block key unique, so the page can key its rows by it', () => {
    const keys = document.blocks.map((block) => block.key);

    expect(new Set(keys).size).toBe(keys.length);
  });

  it('counts words outside comments and estimates the reading time', () => {
    expect(renderer.renderDocument('one two <!-- hidden words -->three', null)).toMatchObject({ wordCount: 3, readMinutes: 1 });

    expect(renderer.renderDocument('word '.repeat(2300), null)).toMatchObject({ wordCount: 2300, readMinutes: 10 });

    expect(renderer.renderDocument('', null)).toMatchObject({ wordCount: 0, readMinutes: 1 });
  });

  it('reads CRLF files like LF files', () => {
    const crlf = renderer.renderDocument(SPEC.replace(/\n/g, '\r\n'), null);

    expect(crlf.meta).toEqual(document.meta);

    expect(crlf.outline).toEqual(document.outline);

    expect(crlf.blocks).toEqual(document.blocks);
  });

  it('ignores a byte order mark at the start of the file', () => {
    const bom = renderer.renderDocument(`\uFEFF${SPEC}`, null);

    expect(bom.titleHtml).toBe(document.titleHtml);

    expect(bom.meta).toEqual(document.meta);

    expect(renderer.renderDocument('\uFEFFPASS ok\n\nbody', 'good').status).toMatchObject({ label: 'PASS ok' });
  });

  it('labels an outline entry with the text of its heading, without html tags', () => {
    expect(renderer.renderDocument('## Using <b>bold</b> and <span class="x">spans</span>', null).outline[0].label).toBe('Using bold and spans');
  });

  it('survives an empty file and a file without a title', () => {
    expect(renderer.renderDocument('', null)).toMatchObject({ titleHtml: null, meta: [], summaryHtml: null, blocks: [], outline: [] });

    expect(renderer.renderDocument('text only', null).titleHtml).toBeNull();
  });

  it('sanitizes the title, the claims, the verifications and the body', () => {
    const hostile = renderer.renderDocument(
      '# T <img src=x onerror="alert(1)">\n\n<script>alert(2)</script>\n\n## Acceptance criteria\n\n1. [ ] <b onclick="alert(3)">c</b> — verify: <iframe src="https://evil.test"></iframe>',
      null,
    );

    const everything = JSON.stringify(hostile);

    for (const bad of ['<script', 'onerror', 'onclick', '<iframe', '<img']) {
      expect(everything).not.toContain(bad);
    }
  });

  it('keeps a reference link whose definition is in another block', () => {
    const linked = renderer.renderDocument('See [the docs][1].\n\n```\ncode\n```\n\n[1]: https://example.test/docs', null);

    expect(htmlOf(linked).join('')).toContain('href="https://example.test/docs"');
  });
});

describe('in-document links', () => {
  it('marks a link to an anchor for the page to scroll to, without opening a new tab', () => {
    const html = renderer.renderMarkdown('[approach](#approach) and [out](https://example.test)');

    expect(html).toContain('href="#approach"');

    expect(html).toContain('data-document-anchor');

    expect(html.match(/target="_blank"/g)).toHaveLength(1);
  });
});

describe('sanitizer hardening', () => {
  it.each(['form', 'input', 'button', 'select', 'textarea', 'img', 'style', 'iframe', 'object', 'embed'])(
    'removes <%s>', (tag) => {
      const html = renderer.renderMarkdown(`before <${tag} src="https://evil.test/x">inner</${tag}> after`);

      expect(html).not.toContain(`<${tag}`);
    });

  it('removes the style attribute but keeps the element', () => {
    const html = renderer.renderMarkdown('<p style="position:fixed;inset:0">covers the page</p>');

    expect(html).toContain('covers the page');

    expect(html).not.toContain('style');
  });

  it('never keeps Alpine-looking attributes', () => {
    const html = renderer.renderMarkdown('<div x-init="alert(1)" x-data="{a:1}" @click="alert(2)" :class="alert(3)" x-html="y" x-on:click="z">text</div>');

    expect(html).toContain('text');

    for (const name of ['x-init', 'x-data', '@click', ':class', 'x-html', 'x-on:click']) {
      expect(html).not.toContain(name);
    }
  });
});
