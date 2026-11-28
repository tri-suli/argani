import type { Navigation } from '@/types/route';

interface Entry {
  hash: string;
  fromBoard: boolean;
}

/** A browser history in memory: push adds an entry, replace rewrites one (keeping its state), Back and Forward move and tell the listener. */
class FakeNavigation implements Navigation {
  entries: Entry[];

  position = 0;

  stopped = false;

  private listener: (() => void) | null = null;

  constructor(initialHash = '') {
    this.entries = [{ hash: initialHash, fromBoard: false }];
  }

  hash(): string {
    return this.entries[this.position].hash;
  }

  fromBoard(): boolean {
    return this.entries[this.position].fromBoard;
  }

  push(hash: string, fromBoard = false): void {
    this.entries = [...this.entries.slice(0, this.position + 1), { hash, fromBoard }];

    this.position += 1;
  }

  replace(hash: string): void {
    this.entries[this.position] = { ...this.entries[this.position], hash };
  }

  back(): void {
    this.position -= 1;

    this.listener?.();
  }

  forward(): void {
    this.position += 1;

    this.listener?.();
  }

  /** The reader edits the address: a new entry without state, and the listener hears of it. */
  edit(hash: string): void {
    this.push(hash);

    this.listener?.();
  }

  listen(listener: () => void): void {
    this.listener = listener;
  }

  stop(): void {
    this.stopped = true;

    this.listener = null;
  }
}

export default FakeNavigation;
