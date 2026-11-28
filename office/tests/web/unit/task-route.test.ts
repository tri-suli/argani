import { describe, expect, it } from 'vitest';
import { buildTaskHash, parseTaskRoute } from '@/board/task-route';
import { BOARD_HASH } from '@/constants/route';

describe('task route', () => {
  it('builds and parses the hash of a task', () => {
    expect(buildTaskHash({ project: 'demo', slug: 'fix-export', path: null })).toBe('#/task/demo/fix-export');

    expect(parseTaskRoute('#/task/demo/fix-export')).toEqual({ project: 'demo', slug: 'fix-export', path: null });
  });

  it('carries the selected file as one encoded segment', () => {
    const hash = buildTaskHash({ project: 'demo', slug: 'ship', path: 'review/round-1/review-code.md' });

    expect(hash).toBe('#/task/demo/ship/review%2Fround-1%2Freview-code.md');

    expect(parseTaskRoute(hash)).toEqual({ project: 'demo', slug: 'ship', path: 'review/round-1/review-code.md' });
  });

  it('encodes every segment so names with slashes, spaces and unicode survive', () => {
    const route = { project: 'my project', slug: 'a/b ü#?', path: 'x y.md' };

    expect(parseTaskRoute(buildTaskHash(route))).toEqual(route);
  });

  it('names the overview of a review round as "round/<n>" after the slug', () => {
    expect(buildTaskHash({ project: 'demo', slug: 'ship', path: null, round: 2 })).toBe('#/task/demo/ship/round/2');

    expect(parseTaskRoute('#/task/demo/ship/round/2')).toEqual({ project: 'demo', slug: 'ship', path: null, round: 2 });

    expect(parseTaskRoute('#/task/my%20project/a%2Fb/round/12')).toEqual({ project: 'my project', slug: 'a/b', path: null, round: 12 });
  });

  it('keeps a file named round a file, and a route without a round has no round', () => {
    expect(parseTaskRoute('#/task/demo/ship/round')).toEqual({ project: 'demo', slug: 'ship', path: 'round' });

    expect(parseTaskRoute('#/task/demo/ship')).not.toHaveProperty('round');
  });

  it.each(['0', '-1', '1.5', 'x', '01', '1e3', ' 2', '99999999999999999999'])('names the task and no round that exists for the round number %j', (number) => {
    expect(parseTaskRoute(`#/task/demo/ship/round/${encodeURIComponent(number)}`)).toEqual({ project: 'demo', slug: 'ship', path: null, round: 0 });
  });

  it.each(['#/task/demo/ship/round/', '#/task/demo/ship/round/2/extra', '#/task/demo/ship/rounds/2'])('is not a task route: %j', (hash) => {
    expect(parseTaskRoute(hash)).toBeNull();
  });

  it.each(['', '#', '#/', '#/board', '#/task', '#/task/demo', '#/task//slug', '#/task/demo/', '#/task/demo/slug/', '#/task/demo/slug/a/b', '#/task/%E0%A4%A/slug', '#/task/demo/slug/%E0%A4%A', '#/other/demo/slug'])('is not a task route: %j', (hash) => {
    expect(parseTaskRoute(hash)).toBeNull();
  });

  it('names the board hash as empty', () => {
    expect(BOARD_HASH).toBe('');
  });
});
