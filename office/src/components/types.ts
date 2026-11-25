import type { BoardSnapshot, BoardTask, ColumnView, FileGroup, FileTone, Poller, RenderedDocument, TaskClient, TaskDetail, TaskFile, TaskSummary } from '../board/types';

export interface DashboardDependencies {
  poller: Poller;
  taskClient: TaskClient;
  now: () => Date;
}

export interface Dashboard {
  snapshot: BoardSnapshot | null;
  tasks: TaskSummary[];
  errorMessage: string | null;
  lastSuccessAt: string | null;
  clockMilliseconds: number;
  selectedProject: string;
  drawer: TaskDrawer;
  init(): void;
  destroy(): void;
  readonly status: string;
  readonly updatedLabel: string;
  readonly projects: string[];
  readonly columns: ColumnView[];
  readonly agentsRunning: number;
  readonly tokensLabel: string;
}

export interface TaskDrawer {
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
