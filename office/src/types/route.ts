/** What the URL hash of the task page names: a task and, optionally, the selected file or the overview of a review round. */
interface TaskRoute {
  project: string;
  slug: string;
  path: string | null;
  /** The review round whose overview is selected; absent for a file and for the task alone. */
  round?: number;
}

/** The browser's address bar and history, as far as the task page needs them. */
interface Navigation {
  /** The current hash, "#/task/..." or "" for the board. */
  hash(): string;
  /** Adds a history entry for the hash; `fromBoard` records in the entry that Back leads to the board. */
  push(hash: string, fromBoard?: boolean): void;
  /** Whether the current entry was added from the board: it is kept in the history state, so it holds across Back, Forward and edits of the address. */
  fromBoard(): boolean;
  /** Rewrites the address of the current entry without adding one or changing its state. */
  replace(hash: string): void;
  back(): void;
  /** Calls the listener whenever the hash changes by Back, Forward or an edit of the address. */
  listen(listener: () => void): void;
  stop(): void;
}

/** The parts of `window` the navigation uses, so a test can hand in a fake. */
interface NavigationWindow {
  location: Pick<Location, 'hash' | 'pathname' | 'search'>;
  history: Pick<History, 'state' | 'pushState' | 'replaceState' | 'back'>;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

export type { TaskRoute, Navigation, NavigationWindow };
