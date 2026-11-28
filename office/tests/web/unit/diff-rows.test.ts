import { describe, expect, it } from 'vitest';
import DiffRows from '@/board/diff-rows';
import type { DiffRowKind } from '@/types/document';

const rows = new DiffRows();

const kinds = (text: string): DiffRowKind[] => rows.parse(text).rows.map((row) => row.kind);

const GIT_DIFF = [
  'diff --git a/a.txt b/a.txt',
  'index 1111111..2222222 100644',
  '--- a/a.txt',
  '+++ b/a.txt',
  '@@ -1,2 +1,2 @@ heading',
  ' same',
  '-old',
  '+new',
  '\\ No newline at end of file',
  'diff --git a/b.bin b/b.bin',
  'Binary files a/b.bin and b/b.bin differ',
  'diff --git a/c.txt b/c.txt',
  '--- a/c.txt',
  '+++ b/c.txt',
  '@@ -1 +1 @@',
  '--- not a header, a removed line starting with dashes',
  '+++ not a header either',
].join('\n');

describe('diff rows', () => {
  it('tells file headers, hunks, added, removed, context, notes and binary lines apart', () => {
    expect(kinds(GIT_DIFF)).toEqual([
      'file', 'file', 'file', 'file', 'hunk', 'context', 'remove', 'add', 'note',
      'file', 'binary',
      'file', 'file', 'file', 'hunk', 'remove', 'add',
    ]);
  });

  it('keeps the text of every line, marker included', () => {
    expect(rows.parse(GIT_DIFF).rows.map((row) => row.text).slice(4, 8)).toEqual(['@@ -1,2 +1,2 @@ heading', ' same', '-old', '+new']);
  });

  it('marks the line that starts each file, for the page to separate the files', () => {
    expect(rows.parse(GIT_DIFF).rows.filter((row) => row.fileStart).map((row) => row.text)).toEqual(['diff --git a/a.txt b/a.txt', 'diff --git a/b.bin b/b.bin', 'diff --git a/c.txt b/c.txt']);
  });

  it('numbers the rows for the page to key them by', () => {
    expect(rows.parse('+a\n-b').rows.map((row) => row.key)).toEqual([0, 1]);
  });

  it('treats a bare patch without headers as added and removed lines', () => {
    expect(kinds('+added line\n-removed line\n')).toEqual(['add', 'remove']);
  });

  it('does not add a row for the newline that ends the file, and handles a file without one', () => {
    expect(rows.parse('+a\n').rows).toHaveLength(1);

    expect(rows.parse('+a\n\n').rows).toHaveLength(2);

    expect(rows.parse('+a').rows).toHaveLength(1);

    expect(rows.parse('').rows).toEqual([]);
  });

  it('strips the carriage return of CRLF lines', () => {
    expect(rows.parse('diff --git a/x b/x\r\n@@ -1 +1 @@\r\n+x\r\n').rows.map((row) => row.text)).toEqual(['diff --git a/x b/x', '@@ -1 +1 @@', '+x']);
  });

  it('marks a git binary patch and keeps its payload in the file header', () => {
    expect(kinds('diff --git a/x b/x\nnew file mode 100644\nGIT binary patch\nliteral 3\nIcmZQz\n')).toEqual(['file', 'file', 'binary', 'file', 'file']);
  });

  it('keeps a blank line inside a hunk as context', () => {
    expect(kinds('@@ -1,3 +1,3 @@\n a\n\n b')).toEqual(['hunk', 'context', 'context', 'context']);
  });

  it('caps what is rendered and says how many lines there are', () => {
    const huge = Array.from({ length: 5000 }, (_, index) => `+line ${index}`).join('\n');

    const view = new DiffRows(100).parse(huge);

    expect(view.rows).toHaveLength(100);

    expect(view).toMatchObject({ total: 5000, truncated: true });

    expect(rows.parse(huge).rows).toHaveLength(1500);

    expect(rows.parse('+a\n+b')).toMatchObject({ total: 2, truncated: false });
  });
});
