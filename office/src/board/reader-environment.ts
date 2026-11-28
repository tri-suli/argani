import { READING_ZONE_MARGIN, REDUCED_MOTION_QUERY } from '@/constants/document';
import type { ReaderEnvironment } from '@/types/document';

/** The browser behind the outline: an IntersectionObserver over a reading zone at the top of the viewport. */
function createBrowserReaderEnvironment(win: Window & typeof globalThis): ReaderEnvironment {
  return {
    createObserver(onChange) {
      return new win.IntersectionObserver(
        (entries) =>
          onChange(
            entries.map((entry) => ({
              id: entry.target.id,
              intersecting: entry.isIntersecting,
              below: !entry.isIntersecting && entry.rootBounds !== null && entry.boundingClientRect.top >= entry.rootBounds.bottom,
            })),
          ),
        { rootMargin: READING_ZONE_MARGIN },
      );
    },

    findElement: (id) => win.document.getElementById(id),

    prefersReducedMotion: () => win.matchMedia(REDUCED_MOTION_QUERY).matches,
  };
}

export default createBrowserReaderEnvironment;
