import { describe, expect, it } from 'vitest';
import RoundSummary from '@/board/round-summary';
import type { RoundTally } from '@/types/round';

const summary = new RoundSummary();

const tally = (overrides: Partial<RoundTally> = {}): RoundTally => ({ seats: 3, passed: 0, changes: 0, pending: 0, invalid: 0, unreadable: 0, read: 0, hasHuman: false, important: 0, nits: 0, other: 0, ...overrides });

describe('round summary', () => {
  it.each<[string, Partial<RoundTally>, string]>([
    ['everyone passed, no findings', { passed: 3, read: 3 }, 'All 3 reviewers passed · no findings'],
    ['everyone passed with nits', { passed: 3, read: 3, nits: 11 }, 'All 3 reviewers passed · 11 nits'],
    ['a single reviewer that passed with one nit', { seats: 1, passed: 1, read: 1, nits: 1 }, 'The reviewer passed · 1 nit'],
    ['some asked for changes', { passed: 1, changes: 2, read: 3, important: 3, nits: 9 }, '2 of 3 reviewers asked for changes · 3 important findings, 9 nits'],
    ['one important finding', { passed: 2, changes: 1, read: 3, important: 1 }, '1 of 3 reviewers asked for changes · 1 important finding'],
    ['all asked for changes', { changes: 3, read: 3, important: 4 }, 'All 3 reviewers asked for changes · 4 important findings'],
    ['the only reviewer asked for changes', { seats: 1, changes: 1, read: 1, important: 2 }, 'The reviewer asked for changes · 2 important findings'],
    ['nobody has reported', { pending: 3 }, 'The reviewers have not reported yet'],
    ['the only reviewer has not reported', { seats: 1, pending: 1 }, 'The reviewer has not reported yet'],
    ['changes and a reviewer still running', { changes: 1, pending: 2, read: 1, important: 1 }, 'Of 3 reviewers: 1 asked for changes, 2 not reported yet · 1 important finding'],
    ['a pass, a change and a pending one', { passed: 1, changes: 1, pending: 1, read: 2, important: 2, nits: 1, other: 1 }, 'Of 3 reviewers: 1 asked for changes, 1 passed, 1 not reported yet · 2 important findings, 1 nit, 1 with another severity'],
    ['an invalid verdict', { passed: 2, invalid: 1, read: 3 }, 'Of 3 reviewers: 2 passed, 1 gave no valid verdict · no findings'],
    ['a file that cannot be read', { passed: 2, pending: 0, changes: 1, read: 2, unreadable: 1, important: 1 }, '1 of 3 reviewers asked for changes · 1 important finding · 1 file could not be read'],
    ['two files that cannot be read', { passed: 3, read: 1, unreadable: 2 }, 'All 3 reviewers passed · 2 files could not be read'],
    ['the human asked for a change, the reviewers have not reported', { pending: 3, read: 1, hasHuman: true, important: 2 }, 'The reviewers have not reported yet · 2 important findings · includes a request from the human'],
    ['the human with the reviewers passed', { passed: 3, read: 4, hasHuman: true, important: 1 }, 'All 3 reviewers passed · 1 important finding · includes a request from the human'],
    ['only the human, no reviewer files', { seats: 0, read: 1, hasHuman: true, important: 1 }, 'Only the human has written a request · 1 important finding'],
    ['no files at all', { seats: 0 }, 'No review file in this round yet'],
  ])('says it for %s', (_name, overrides, expected) => {
    expect(summary.sentence(tally(overrides))).toBe(expected);
  });

  it('never says no findings when nothing has been read', () => {
    expect(summary.sentence(tally({ pending: 3, read: 0 }))).not.toContain('no findings');
  });
});
