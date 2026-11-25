import type { BoardTask } from '@/types/board';
import type { FileTone, ReviewState, Risk, TaskFile } from '@/types/task';

interface PipelineColumn {
  name: string;
  who: string;
  tone: '' | 'human' | 'merged';
}

interface ChipView {
  reviewer: string;
  state: ReviewState;
  className: string;
}

interface RoundView {
  n: number;
  label: string;
  chips: ChipView[];
}

interface CardView {
  key: string;
  task: BoardTask;
  active: boolean;
  risk: Risk | null;
  rounds: RoundView[];
  mrUrl: string | null;
  time: string;
  tokens: string;
  flag: string | null;
  hint: string | null;
  dimmed: boolean;
}

interface ColumnView {
  name: string;
  who: string;
  tone: '' | 'human' | 'merged';
  cards: CardView[];
}

interface FileGroup {
  name: string;
  files: TaskFile[];
}

interface RenderedDocument {
  /** First line of the file, shown as a badge, when the file has a tone. */
  verdict: string | null;
  tone: FileTone | null;
  /** The `## Summary` section, if any. */
  summaryHtml: string | null;
  bodyHtml: string;
}

export type { PipelineColumn, ChipView, RoundView, CardView, ColumnView, FileGroup, RenderedDocument };
