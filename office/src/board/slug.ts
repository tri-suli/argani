import { EDGE_DASH_PATTERN, FALLBACK_SECTION_SLUG, NON_SLUG_PATTERN, SLUG_SEPARATOR } from '@/constants/document';

/** The slug of a heading's text, which is also what an in-document link is matched on: lowercase letters and digits joined by dashes. */
function slugOf(text: string): string {
  return text.toLowerCase().replace(NON_SLUG_PATTERN, SLUG_SEPARATOR).replace(EDGE_DASH_PATTERN, '') || FALLBACK_SECTION_SLUG;
}

export default slugOf;
