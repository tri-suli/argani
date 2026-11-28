/** What the URL hash of the task page names: a task and, optionally, the selected file. */
interface TaskRoute {
  project: string;
  slug: string;
  path: string | null;
}

/** The browser's address bar and history, as far as the task page needs them. */
interface Navigation {
  /** The current hash, "#/task/..." or "" for the board. */
  hash(): string;
  /** Adds a history entry for the hash. */
  push(hash: string): void;
  /** Rewrites the current entry without adding one. */
  replace(hash: string): void;
  back(): void;
  /** Calls the listener whenever the hash changes by Back, Forward or an edit of the address. */
  listen(listener: () => void): void;
  stop(): void;
}

/** The parts of `window` the navigation uses, so a test can hand in a fake. */
interface NavigationWindow {
  location: Pick<Location, 'hash' | 'pathname' | 'search'>;
  history: Pick<History, 'pushState' | 'replaceState' | 'back'>;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

export type { TaskRoute, Navigation, NavigationWindow };
