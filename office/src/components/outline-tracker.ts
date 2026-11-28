import { ANCHOR_SELECTOR, IN_ZONE, NOT_FOUND_INDEX, PASSED, DOCUMENT_ID_PREFIX, FIRST_INDEX, FRAGMENT_PREFIX, INSTANT_SCROLL, SMOOTH_SCROLL } from '@/constants/document';
import type { OutlineTracker, ReaderEnvironment, SectionObserver } from '@/types/document';

function decodedFragment(fragment: string): string {
  try {
    return decodeURIComponent(fragment);
  } catch {
    return fragment;
  }
}

/** UI state only: the observer, the lookup of elements and the motion preference are injected. */
function createOutlineTracker(environment: ReaderEnvironment): OutlineTracker {
  let observer: SectionObserver | null = null;

  let stopWatchingScroll: (() => void) | null = null;

  let sectionIds: string[] = [];

  // the section the reader clicked: it stays highlighted while it is on its way and while it is in the zone,
  // because at the end of the page an earlier section can share the zone with it
  let pinnedId: string | null = null;

  let pinArrived = false;

  return {
    activeId: null,

    track(ids) {
      this.stop();

      sectionIds = ids;

      pinnedId = null;

      observer = environment.createObserver(() => this.change());

      // the observer misses a jump that crosses no edge of the zone (End key, a dragged scrollbar)
      stopWatchingScroll = environment.watchScroll({ onScroll: () => this.change() });

      for (const id of ids) {
        const element = environment.findElement(id);

        if (element !== null) {
          observer.observe(element);
        }
      }

      // an open reader starts at its first section; a section that survived a re-render keeps the highlight
      this.activeId = this.activeId !== null && ids.includes(this.activeId) ? this.activeId : (ids[FIRST_INDEX] ?? null);
    },

    stop() {
      observer?.disconnect();

      observer = null;

      stopWatchingScroll?.();

      stopWatchingScroll = null;
    },

    scrollTo(id) {
      const element = environment.findElement(id);

      if (element === null) {
        return;
      }

      if (sectionIds.includes(id)) {
        this.activeId = id;

        pinnedId = id;

        pinArrived = environment.positionOf(id) === IN_ZONE;
      }

      element.scrollIntoView({ behavior: environment.prefersReducedMotion() ? INSTANT_SCROLL : SMOOTH_SCROLL, block: 'start' });
    },

    followAnchor(event) {
      const anchor = (event.target as Element).closest(ANCHOR_SELECTOR);

      if (anchor === null) {
        return;
      }

      // the address hash is the route: the browser must not follow the link
      event.preventDefault();

      this.scrollTo(DOCUMENT_ID_PREFIX + decodedFragment((anchor.getAttribute('href') as string).slice(FRAGMENT_PREFIX.length)));
    },

    change() {
      const positions = sectionIds.map((id) => environment.positionOf(id));

      if (pinnedId !== null) {
        if (environment.positionOf(pinnedId) === IN_ZONE) {
          pinArrived = true;

          this.activeId = pinnedId;

          return;
        }

        if (!pinArrived) {
          return;
        }

        pinnedId = null;
      }

      // the first heading in the zone; else the last one the reader has passed; else the page has not reached the first
      const inZone = positions.indexOf(IN_ZONE);

      const passed = positions.lastIndexOf(PASSED);

      this.activeId = sectionIds[inZone !== NOT_FOUND_INDEX ? inZone : Math.max(passed, FIRST_INDEX)] ?? null;
    },
  };
}

export default createOutlineTracker;
