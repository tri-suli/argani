import type { BoardTask } from '@/types/board';
import type { DocumentBlock, DocumentStatus, MetaEntry, OutlineEntry } from '@/types/document';
import type { ReviewState, Risk, TaskFile } from '@/types/task';

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
  agents: AgentView[];
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

/** The pills and metrics of the task page header; an empty string means the data does not state it. */
interface TaskHeaderView {
  column: string;
  /** "round 3", only while the task is in Review. */
  round: string;
  stage: string;
  risk: Risk | null;
  riskIcon: string;
  time: string;
  tokens: string;
  manual: string;
  /** "2× needed you · 25m"; empty when the task never waited for the human. */
  visits: string;
  mrUrl: string | null;
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
  /** The pill of the head: the `Status:` value, else the first line of a file that has a tone. */
  status: DocumentStatus | null;
  /** The first `# ` heading as sanitized inline html. */
  titleHtml: string | null;
  meta: MetaEntry[];
  /** The `## Summary` section, if any, and the id its heading would have. */
  summaryHtml: string | null;
  summaryId: string | null;
  blocks: DocumentBlock[];
  outline: OutlineEntry[];
  wordCount: number;
  readMinutes: number;
}

export type { TaskHeaderView, PipelineColumn, ChipView, RoundView, AgentView, CardView, TileTone, TotalsTile, NeedsHumanRow, DoneRow, ProjectOption, ColumnView, FileGroup, RenderedDocument };
