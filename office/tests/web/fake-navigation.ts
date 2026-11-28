import type { Navigation } from '@/types/route';

/** A browser history in memory: push adds an entry, replace rewrites one, Back and Forward move and tell the listener. */
class FakeNavigation implements Navigation {
  entries: string[];

  position = 0;

  stopped = false;

  private listener: (() => void) | null = null;

  constructor(initialHash = '') {
    this.entries = [initialHash];
  }

  hash(): string {
    return this.entries[this.position];
  }

  push(hash: string): void {
    this.entries = [...this.entries.slice(0, this.position + 1), hash];

    this.position += 1;
  }

  replace(hash: string): void {
    this.entries[this.position] = hash;
  }

  back(): void {
    this.position -= 1;

    this.listener?.();
  }

  forward(): void {
    this.position += 1;

    this.listener?.();
  }

  /** The reader edits the address: a new entry, and the listener hears of it. */
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
