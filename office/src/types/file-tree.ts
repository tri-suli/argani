/** What the icon and colour of a row say: a tone of its first line, "none" for no verdict, "now" for a running round. */
type RowTone = 'good' | 'warn' | 'stop' | 'none' | 'now';

interface FileRow {
  key: string;
  kind: 'file' | 'round';
  label: string;
  /** Icon-font ligature. */
  icon: string;
  tone: RowTone;
  /** The verdict word at the right: "PASS", "CHANGES", "running"; empty when there is none. */
  tag: string;
  /** The whole first line of a file, for the tooltip. */
  tagTitle: string;
  /** A file below its round. */
  nested: boolean;
  /** The file this row opens; null for a round. */
  path: string | null;
  /** The round this row stands for; null for a file. */
  round: number | null;
  expanded: boolean;
  /** A running round: the icon turns. */
  spinning: boolean;
  /** The tone in words for screen readers; empty when the row has none. */
  toneLabel: string;
}

interface FileSection {
  name: string;
  rows: FileRow[];
}

export type { RowTone, FileRow, FileSection };
