import type BoardView from '@/board/board-view';
import type MarkdownRenderer from '@/board/markdown-renderer';
import type { BoardSnapshot, BoardTask } from '@/types/board';
import type { TaskClient } from '@/types/client';
import type { Poller } from '@/types/poller';
import type { FileTone, TaskDetail, TaskFile, TaskSummary } from '@/types/task';
import type { ColumnView, DoneRow, FileGroup, HistoryRow, NeedsHumanRow, ProjectOption, RenderedDocument, TotalsTile } from '@/types/view';

interface DashboardDependencies {
  poller: Poller;
  taskClient: TaskClient;
  boardView: BoardView;
  markdownRenderer: MarkdownRenderer;
  clipboard: ClipboardWriter;
  now: () => Date;
}

interface ClipboardWriter {
  writeText(text: string): Promise<void>;
}

interface CommandCopier {
  /** The command copied last, until its feedback runs out. */
  key: string | null;
  failed: boolean;
  copy(key: string, command: string): Promise<void>;
  isCopied(key: string): boolean;
  /** "Copy", "Copied" or "Copy failed" for the button of this command. */
  label(key: string): string;
}

interface ProjectPicker {
  isOpen: boolean;
  /** The text typed in the search field. */
  query: string;
  toggle(): void;
  close(): void;
  navigate(event: KeyboardEvent, container: HTMLElement): void;
}

interface Dashboard {
  snapshot: BoardSnapshot | null;
  tasks: TaskSummary[];
  errorMessage: string | null;
  lastSuccessAt: string | null;
  clockMilliseconds: number;
  selectedProject: string;
  drawer: TaskDrawer;
  picker: ProjectPicker;
  copier: CommandCopier;
  init(): void;
  destroy(): void;
  readonly status: string;
  readonly updatedLabel: string;
  /** Every project option, and the ones the search field leaves. */
  readonly projectOptions: ProjectOption[];
  readonly matchingProjectOptions: ProjectOption[];
  readonly selectedOption: ProjectOption;
  readonly columns: ColumnView[];
  readonly tiles: TotalsTile[];
  readonly needsHumanRows: NeedsHumanRow[];
  readonly doneRows: DoneRow[];
  /** Filters the board to the project and closes the picker, giving the focus back to its button. */
  chooseProject(value: string, button: HTMLElement): void;
  closePicker(button: HTMLElement): void;
  /** The task open in the drawer, read from the latest board so its history stays current. */
  readonly drawerTask: BoardTask | null;
  readonly drawerWaiting: string;
  readonly drawerHasHistory: boolean;
  readonly drawerHistory: HistoryRow[];
}

interface TaskDrawer {
  isOpen: boolean;
  project: string;
  slug: string;
  title: string;
  detail: TaskDetail | null;
  selectedPath: string | null;
  fileText: string;
  /** Path and fingerprint (updatedAt, listing entry) of the file now in fileText/rendered; null when none is loaded. */
  loadedPath: string | null;
  loadedStamp: string | null;
  /** Rendered markdown of the selected file; null when it is shown as plain text. */
  rendered: RenderedDocument | null;
  errorMessage: string | null;
  /** Bumped by every request so a slow answer for an old selection is dropped. */
  generation: number;
  open(task: BoardTask): Promise<void>;
  close(): void;
  select(path: string): Promise<void>;
  /** Reloads the open task, called after every board poll. */
  refresh(): Promise<void>;
  trapFocus(event: KeyboardEvent, container: HTMLElement): void;
  clearFile(): void;
  fileStamp(detail: TaskDetail): string;
  load(): Promise<void>;
  loadFile(generation: number): Promise<void>;
  readonly headline: string;
  readonly groups: FileGroup[];
  readonly selectedFile: TaskFile | null;
  fileLabel(file: TaskFile): string;
  toneLabel(tone: FileTone | null): string;
}

export type { DashboardDependencies, Dashboard, TaskDrawer, ClipboardWriter, CommandCopier, ProjectPicker };
