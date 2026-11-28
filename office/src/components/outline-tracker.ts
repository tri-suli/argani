import { ANCHOR_SELECTOR, DOCUMENT_ID_PREFIX, FIRST_INDEX, FRAGMENT_PREFIX, INSTANT_SCROLL, SMOOTH_SCROLL } from '@/constants/document';
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

  let sectionIds: string[] = [];

  let inZone = new Set<string>();

  return {
    activeId: null,

    track(ids) {
      this.stop();

      sectionIds = ids;

      inZone = new Set();

      observer = environment.createObserver((entries) => this.change(entries));

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
    },

    scrollTo(id) {
      const element = environment.findElement(id);

      if (element === null) {
        return;
      }

      if (sectionIds.includes(id)) {
        this.activeId = id;
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

    change(entries) {
      let scrolledBack = false;

      for (const entry of entries) {
        if (entry.intersecting) {
          inZone.add(entry.id);
        } else {
          inZone.delete(entry.id);

          scrolledBack = scrolledBack || (entry.below && entry.id === this.activeId);
        }
      }

      const inView = sectionIds.find((id) => inZone.has(id));

      if (inView !== undefined) {
        this.activeId = inView;
      } else if (scrolledBack) {
        const above = sectionIds.indexOf(this.activeId as string) - 1;

        this.activeId = sectionIds[above] ?? sectionIds[FIRST_INDEX];
      }
    }
  };
}

export default createOutlineTracker;
