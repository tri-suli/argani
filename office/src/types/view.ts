import type { BoardTask } from '@/types/board';
import type { FileTone, ReviewState, Risk, TaskFile } from '@/types/task';

interface PipelineColumn {
  /** "01" to "05": the position in the pipeline. */
  step: string;
  name: string;
  who: string;
}

interface ChipView {
  reviewer: string;
  state: ReviewState;
  className: string;
  icon: string;
}

interface RoundView {
  n: number;
  label: string;
  chips: ChipView[];
}

/** An agent running on a task, with the time since it was spawned. */
interface AgentView {
  id: string;
  name: string;
  elapsed: string;
}

interface CardView {
  key: string;
  task: BoardTask;
  active: boolean;
  risk: Risk | null;
  riskIcon: string;
  rounds: RoundView[];
  agents: AgentView[];
  mrUrl: string | null;
  time: string;
  tokens: string;
}

type TileTone = '' | 'active' | 'human';

interface TotalsTile {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: TileTone;
}

/** One task waiting for an answer, longest wait first. */
interface NeedsHumanRow {
  key: string;
  task: BoardTask;
  reason: string;
  /** "14m"; empty when the task has no history to measure from. */
  waiting: string;
  question: string | null;
  /** "2× you" once the task has waited for the human before; empty otherwise. */
  visits: string;
  command: string;
}

interface DoneRow {
  key: string;
  task: BoardTask;
  cancelled: boolean;
  outcome: string;
  icon: string;
  /** Agent time; empty when unknown. */
  time: string;
}

interface ProjectOption {
  /** The project name; empty for "All projects". */
  value: string;
  label: string;
  count: number;
  waiting: number;
}

interface HistoryRow {
  column: string;
  duration: string;
}

interface ColumnView {
  step: string;
  name: string;
  who: string;
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

export type { HistoryRow, PipelineColumn, ChipView, RoundView, AgentView, CardView, TileTone, TotalsTile, NeedsHumanRow, DoneRow, ProjectOption, ColumnView, FileGroup, RenderedDocument };
