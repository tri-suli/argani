import type BoardView from '@/board/board-view';
import type FileTree from '@/board/file-tree';
import type HistorySteps from '@/board/history-steps';
import type DiffRows from '@/board/diff-rows';
import type MarkdownRenderer from '@/board/markdown-renderer';
import type { BoardSnapshot, BoardTask } from '@/types/board';
import type { CodeBlock, DiffView, OutlineTracker, ReaderEnvironment } from '@/types/document';
import type { TaskClient } from '@/types/client';
import type { Poller } from '@/types/poller';
import type { FileSection } from '@/types/file-tree';
import type { HistoryStep, LegendEntry } from '@/types/history';
import type { Navigation, TaskRoute } from '@/types/route';
import type { TaskDetail, TaskFile, TaskSummary } from '@/types/task';
import type { ColumnView, DoneRow, NeedsHumanRow, ProjectOption, RenderedDocument, TaskHeaderView, TotalsTile } from '@/types/view';

interface DashboardDependencies {
  poller: Poller;
  taskClient: TaskClient;
  boardView: BoardView;
  historySteps: HistorySteps;
  fileTree: FileTree;
  navigation: Navigation;
  markdownRenderer: MarkdownRenderer;
  diffRows: DiffRows;
  readerEnvironment: ReaderEnvironment;
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
  taskPage: TaskPage;
  /** The colour legend of the history strip. */
  legend: LegendEntry[];
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
  /** Opens the task page for the task of a card or row, remembering where the board was scrolled. */
  openTask(task: BoardTask): void;
  /** The "← Board" button: back in the history when the task was opened from the board, otherwise straight to the board. */
  leaveTask(): void;
  /** Picks a file of the open task and puts it in the address. */
  selectFile(path: string): Promise<void>;
  /** Shows the task or the board the address names. */
  applyRoute(): void;
  /** Puts the file really shown in the address when the route named one the task does not list. */
  correctAddress(route: TaskRoute, hash: string): void;
  /** The task open on the task page, read from the latest board so its title and history stay current. */
  readonly taskPageTask: BoardTask | null;
  /** The summary of the open task: the detail once it is loaded, the board's list until then. */
  readonly taskSummary: TaskSummary | null;
  readonly taskTitle: string;
  /** The title of the browser tab: the task while one is open, the app otherwise. */
  readonly documentTitle: string;
  /** The open task is not on the board (any more), once a board has been received. */
  readonly taskMissing: boolean;
  readonly taskHeader: TaskHeaderView | null;
  readonly taskHistory: HistoryStep[];
}

interface TaskPage {
  isOpen: boolean;
  project: string;
  slug: string;
  detail: TaskDetail | null;
  selectedPath: string | null;
  fileText: string;
  /** Path and fingerprint (updatedAt, listing entry) of the file now in fileText/rendered; null when none is loaded. */
  loadedPath: string | null;
  loadedStamp: string | null;
  /** Rendered markdown of the selected file; null when it is shown as plain text. */
  rendered: RenderedDocument | null;
  /** Rows of the selected file when it is a diff; null for every other file. */
  diff: DiffView | null;
  /** The reader's outline: which section is in view, and scrolling to one. */
  outline: OutlineTracker;
  errorMessage: string | null;
  /** Bumped by every request so a slow answer for an old selection is dropped. */
  generation: number;
  /** The review rounds whose files are listed; null until the first load of the task has chosen them. */
  openRounds: number[] | null;
  /** The round numbers listed at the last load, to tell a round that has just appeared from one the reader has seen. */
  knownRounds: number[];
  /** Where the board was scrolled when the task was opened from it. */
  boardScrollY: number;
  /** Counts the opens and the closes, so the page can move the focus once per change. */
  openCount: number;
  closeCount: number;
  open(route: TaskRoute): Promise<void>;
  /** Shows the task of the route: opens it, or only changes the file when it is the task already open. */
  show(route: TaskRoute): Promise<void>;
  /** Leaves the task page; the board comes back and the page restores it. */
  hide(): void;
  /** Remembers where the board was scrolled, to restore it when the task page is left. */
  rememberBoardPosition(scrollY: number): void;
  /** Scrolls the board to where it was and returns the focus to the element that opened the task. */
  restoreBoard(): void;
  focusTitle(title: HTMLElement): void;
  select(path: string): Promise<void>;
  toggleRound(round: number): void;
  /** Reloads the open task, called after every board poll. */
  refresh(): Promise<void>;
  /** Chooses the rounds shown open: at the first load, and for a running round that has appeared since. */
  chooseOpenRounds(detail: TaskDetail): void;
  clearFile(): void;
  fileStamp(detail: TaskDetail): string;
  load(): Promise<void>;
  loadFile(generation: number): Promise<void>;
  readonly sections: FileSection[];
  readonly selectedFile: TaskFile | null;
  /** The name of the selected file without its folders. */
  readonly selectedFileName: string;
  /** The ids of the outline sections of the rendered document. */
  readonly sectionIds: string[];
  /** What the Copy feedback of a code block is filed under: the file, the place and the text, so a changed document never shows it on another block. */
  copyKey(block: CodeBlock): string;
  /** Has the outline observe the headings once the page has drawn them. */
  trackSections(): void;
}

export type { DashboardDependencies, Dashboard, TaskPage, ClipboardWriter, CommandCopier, ProjectPicker };
