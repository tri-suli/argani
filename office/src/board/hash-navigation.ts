import { BOARD_HASH, POP_STATE_EVENT } from '@/constants/route';
import type { Navigation } from '@/types/route';

/** The parts of `window` the navigation uses, so a test can hand in a fake. */
type NavigationWindow = Pick<Window, 'location' | 'history' | 'addEventListener' | 'removeEventListener'>;

/** The hash of the page as a history of its own: the task page is a place the Back button leaves. */
class HashNavigation implements Navigation {
  private listener: (() => void) | null = null;

  constructor(private readonly browser: NavigationWindow) {}

  hash(): string {
    return this.browser.location.hash;
  }

  push(hash: string): void {
    this.browser.history.pushState(null, '', this.address(hash));
  }

  replace(hash: string): void {
    this.browser.history.replaceState(null, '', this.address(hash));
  }

  back(): void {
    this.browser.history.back();
  }

  // pushState and replaceState fire no event, so only Back, Forward and an edited address reach the listener
  listen(listener: () => void): void {
    this.listener = listener;

    this.browser.addEventListener(POP_STATE_EVENT, listener);
  }

  stop(): void {
    if (this.listener !== null) {
      this.browser.removeEventListener(POP_STATE_EVENT, this.listener);

      this.listener = null;
    }
  }

  /** The address of this page with the hash; the board has none, so no bare "#" is left behind. */
  private address(hash: string): string {
    return `${this.browser.location.pathname}${this.browser.location.search}${hash === BOARD_HASH ? '' : hash}`;
  }
}

export default HashNavigation;
