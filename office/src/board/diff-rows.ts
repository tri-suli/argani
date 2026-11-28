import {
  DIFF_ADD_MARKER, DIFF_BINARY_STARTS, DIFF_FILE_MARKERS, DIFF_FILE_START, DIFF_HUNK_START, DIFF_NOTE_MARKER, DIFF_REMOVE_MARKER, DIFF_ROW_LIMIT,
  LINE_BREAK, TRAILING_CARRIAGE_RETURN,
} from '@/constants/document';
import type { DiffRow, DiffRowKind, DiffView } from '@/types/document';

/**
 * Tells the lines of a unified diff apart without highlighting inside them, so a large diff stays cheap.
 * shortcut: a diff of several files without `diff ` lines (plain `diff -u`) reads the `--- `/`+++ ` lines of its
 * second file as removed and added lines; upgrade by counting the hunk lengths if such input ever shows up.
 */
class DiffRows {
  constructor(private readonly limit: number = DIFF_ROW_LIMIT) {}

  parse(text: string): DiffView {
    const lines = text.split(LINE_BREAK);

    if (lines[lines.length - 1] === '') {
      lines.pop();
    }

    let inHeader = true;

    const rows: DiffRow[] = lines.slice(0, this.limit).map((line, key) => {
      const text = line.replace(TRAILING_CARRIAGE_RETURN, '');

      const kind = this.kindOf(text, inHeader);

      inHeader = this.isHeaderAfter(kind, inHeader);

      return { key, kind, text };
    });

    return { rows, total: lines.length, truncated: lines.length > this.limit };
  }

  /** The header of a file runs from its `diff ` line to its first hunk. */
  private isHeaderAfter(kind: DiffRowKind, inHeader: boolean): boolean {
    if (kind === 'file') {
      return true;
    }

    return kind === 'binary' || kind === 'note' ? inHeader : false;
  }

  private kindOf(line: string, inHeader: boolean): DiffRowKind {
    if (line.startsWith(DIFF_FILE_START)) {
      return 'file';
    }

    if (line.startsWith(DIFF_HUNK_START)) {
      return 'hunk';
    }

    if (DIFF_BINARY_STARTS.some((start) => line.startsWith(start))) {
      return 'binary';
    }

    if (inHeader && !this.isChange(line)) {
      return 'file';
    }

    if (inHeader && DIFF_FILE_MARKERS.some((marker) => line.startsWith(marker))) {
      return 'file';
    }

    if (line.startsWith(DIFF_ADD_MARKER)) {
      return 'add';
    }

    if (line.startsWith(DIFF_REMOVE_MARKER)) {
      return 'remove';
    }

    return line.startsWith(DIFF_NOTE_MARKER) ? 'note' : 'context';
  }

  private isChange(line: string): boolean {
    return line.startsWith(DIFF_ADD_MARKER) || line.startsWith(DIFF_REMOVE_MARKER);
  }
}

export default DiffRows;
