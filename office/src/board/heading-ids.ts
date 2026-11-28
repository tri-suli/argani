import slugOf from '@/board/slug';
import { DOCUMENT_ID_PREFIX, SLUG_SEPARATOR } from '@/constants/document';

/** Hands out the ids of one document's headings: readable, prefixed so they never collide with the page's own ids, unique. */
class HeadingIds {
  private readonly taken = new Set<string>();

  next(label: string): string {
    const slug = slugOf(label);

    let id = DOCUMENT_ID_PREFIX + slug;

    for (let copy = 2; this.taken.has(id); copy += 1) {
      id = `${DOCUMENT_ID_PREFIX}${slug}${SLUG_SEPARATOR}${copy}`;
    }

    this.taken.add(id);

    return id;
  }
}

export default HeadingIds;
