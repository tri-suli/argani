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

export type { TaskRoute, Navigation };
