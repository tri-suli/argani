import { describe, expect, it } from 'vitest';
import DocumentHead from '@/board/document-head';

const head = new DocumentHead();

// the head of plugins/argani/templates/spec.md, filled in
const SPEC = '# Spec: Install Laravel\n\nIntent: install-laravel\nStatus: approved by argani on 2026-11-26\nDate: 2026-11-26\n\n## Summary\n\nText.';

describe('document head', () => {
  it('takes the title and the Key: value block that follows it', () => {
    expect(head.split(SPEC, false)).toEqual({
      verdict: null,
      title: 'Spec: Install Laravel',
      meta: [
        { key: 'Intent', value: 'install-laravel' },
        { key: 'Status', value: 'approved by argani on 2026-11-26' },
        { key: 'Date', value: '2026-11-26' },
      ],
      body: '\n## Summary\n\nText.',
    });
  });

  it('keeps colons in the value and in a value that looks like a key', () => {
    const parts = head.split('# T\n\nMR: https://example.test/a/b: c\nNote: Status: x\n\nbody', false);

    expect(parts.meta).toEqual([{ key: 'MR', value: 'https://example.test/a/b: c' }, { key: 'Note', value: 'Status: x' }]);
  });

  it('reads the block of a decision, which has a verdict line and no title', () => {
    const parts = head.split('APPROVE all three pass\nRound: 1\n\n## Reviewers\n- code: PASS', true);

    expect(parts).toMatchObject({ verdict: 'APPROVE all three pass', title: null, meta: [{ key: 'Round', value: '1' }], body: '\n## Reviewers\n- code: PASS' });
  });

  it('leaves the first line alone when the file has no verdict line', () => {
    expect(head.split('Round: 1\n\nbody', false).meta).toEqual([{ key: 'Round', value: '1' }]);
  });

  it('does not take a Key: value line later in the body', () => {
    const parts = head.split('# T\n\nSome prose first.\n\nStatus: draft\n', false);

    expect(parts.meta).toEqual([]);

    expect(parts.body).toContain('Status: draft');
  });

  it('leaves a paragraph that only starts with a Key: value line in the body', () => {
    const parts = head.split('# T\n\nNote: this is prose\nthat goes on.\n', false);

    expect(parts.meta).toEqual([]);

    expect(parts.body).toBe('\nNote: this is prose\nthat goes on.\n');
  });

  it('takes a block that ends the file', () => {
    expect(head.split('# T\nStatus: draft', false)).toMatchObject({ meta: [{ key: 'Status', value: 'draft' }], body: '' });
  });

  it('has no title or meta when the file starts with something else', () => {
    expect(head.split('Just text', false)).toEqual({ verdict: null, title: null, meta: [], body: 'Just text' });

    expect(head.split('## Summary\n\nx', false).title).toBeNull();
  });

  it('survives an empty file and an empty title', () => {
    expect(head.split('', false)).toEqual({ verdict: null, title: null, meta: [], body: '' });

    expect(head.split('', true)).toMatchObject({ verdict: '', title: null });

    expect(head.split('# \n\nbody', false).title).toBeNull();
  });

  it('does not take a key that is not a word or is too long', () => {
    expect(head.split('# T\n\n- a: b\n', false).meta).toEqual([]);

    expect(head.split(`# T\n\n${'k'.repeat(40)}: b\n`, false).meta).toEqual([]);
  });
});
