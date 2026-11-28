import { FILE_SEGMENT_INDEX, MAX_ROUTE_SEGMENTS, MIN_ROUTE_SEGMENTS, ROUTE_SEPARATOR, TASK_HASH_PREFIX } from '@/constants/route';
import type { TaskRoute } from '@/types/route';

/** "#/task/<project>/<slug>[/<file>]", every segment encoded, the file path as one segment. */
function buildTaskHash({ project, slug, path }: TaskRoute): string {
  const segments = path === null ? [project, slug] : [project, slug, path];

  return TASK_HASH_PREFIX + segments.map(encodeURIComponent).join(ROUTE_SEPARATOR);
}

/** The task a hash names; null for the board and for anything that is not a well-formed task hash. */
function parseTaskRoute(hash: string): TaskRoute | null {
  if (!hash.startsWith(TASK_HASH_PREFIX)) {
    return null;
  }

  const segments = hash.slice(TASK_HASH_PREFIX.length).split(ROUTE_SEPARATOR);

  if (segments.length < MIN_ROUTE_SEGMENTS || segments.length > MAX_ROUTE_SEGMENTS || segments.some((segment) => segment === '')) {
    return null;
  }

  try {
    const [project, slug, path] = segments.map(decodeURIComponent);

    return { project, slug, path: segments.length > FILE_SEGMENT_INDEX ? path : null };
  } catch {
    return null; // a malformed escape such as %E0%A4%A
  }
}

export { buildTaskHash, parseTaskRoute };
