import { DOCUMENT_ID_PREFIX, EDGE_DASH_PATTERN, FALLBACK_SECTION_SLUG, NON_SLUG_PATTERN, SLUG_SEPARATOR } from '@/constants/document';

/** Hands out the ids of one document's headings: readable, prefixed so they never collide with the page's own ids, unique. */
class HeadingIds {
  private readonly taken = new Set<string>();

  next(label: string): string {
    const slug = label.toLowerCase().replace(NON_SLUG_PATTERN, SLUG_SEPARATOR).replace(EDGE_DASH_PATTERN, '') || FALLBACK_SECTION_SLUG;

    let id = DOCUMENT_ID_PREFIX + slug;

    for (let copy = 2; this.taken.has(id); copy += 1) {
      id = `${DOCUMENT_ID_PREFIX}${slug}${SLUG_SEPARATOR}${copy}`;
    }

    this.taken.add(id);

    return id;
  }
}

export default HeadingIds;
