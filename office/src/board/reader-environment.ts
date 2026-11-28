import { IN_ZONE, NOT_REACHED, PASSED, PERCENT, READING_ZONE_MARGIN, READING_ZONE_PERCENT, REDUCED_MOTION_QUERY } from '@/constants/document';
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

    prefersReducedMotion: () => win.matchMedia(REDUCED_MOTION_QUERY).matches,
  };
}

export default createBrowserReaderEnvironment;
