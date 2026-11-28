import { describe, expect, it } from 'vitest';
import roundOutcome from '@/board/review-outcome';

describe('round outcome', () => {
  it.each([
    [{ code: 'PASS', docs: 'PASS' }, 'PASS'],
    [{ code: 'PASS', docs: 'CHANGES' }, 'CHANGES'],
    [{ code: 'pending', docs: 'CHANGES' }, 'CHANGES'],
    [{ code: 'PASS', docs: 'pending' }, null],
    [{ code: 'PASS', docs: 'invalid' }, null],
    [{}, null],
  ] as const)('reads %j as %s', (reviews, outcome) => {
    expect(roundOutcome({ n: 1, reviews })).toBe(outcome);
  });

  it('has no outcome for a round that does not exist', () => {
    expect(roundOutcome(undefined)).toBeNull();
  });
});
