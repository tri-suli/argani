import { IN_ZONE, NOT_REACHED, PASSED, PERCENT, READING_ZONE_MARGIN, PAGE_END_TOLERANCE_PIXELS, READING_ZONE_PERCENT, REDUCED_MOTION_QUERY, SCROLL_SETTLE_MILLISECONDS } from '@/constants/document';
import type { ReaderEnvironment, SectionPosition } from '@/types/document';

/** The browser behind the outline: an IntersectionObserver over a reading zone at the top of the viewport. */
function createBrowserReaderEnvironment(win: Window & typeof globalThis): ReaderEnvironment {
  const findElement = (id: string) => win.document.getElementById(id);

  return {
    createObserver(onChange) {
      return new win.IntersectionObserver(() => onChange(), { rootMargin: READING_ZONE_MARGIN });
    },

    findElement,

    positionOf(id): SectionPosition {
      const box = findElement(id)?.getBoundingClientRect();

      if (box === undefined || box.top > (win.innerHeight * READING_ZONE_PERCENT) / PERCENT) {
        return NOT_REACHED;
      }

      return box.bottom < 0 ? PASSED : IN_ZONE;
    },

    watchScroll({ onScroll, onSettled }) {
      let frameRequested = false;

      let settleTimer: ReturnType<typeof setTimeout> | undefined;

      const listener = () => {
        if (!frameRequested) {
          frameRequested = true;

          win.requestAnimationFrame(() => {
            frameRequested = false;

            onScroll();
          });
        }

        // no native scrollend everywhere: the scrolling has settled when no scroll event came for a moment
        clearTimeout(settleTimer);

        settleTimer = setTimeout(onSettled, SCROLL_SETTLE_MILLISECONDS);
      };

      win.addEventListener('scroll', listener, { passive: true });

      return () => {
        win.removeEventListener('scroll', listener);

        clearTimeout(settleTimer);
      };
    },

    isAtPageEnd: () => win.scrollY + win.innerHeight >= win.document.documentElement.scrollHeight - PAGE_END_TOLERANCE_PIXELS,

    prefersReducedMotion: () => win.matchMedia(REDUCED_MOTION_QUERY).matches,
  };
}

export default createBrowserReaderEnvironment;
