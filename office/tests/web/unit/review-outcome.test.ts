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

  it.each([
    [{ code: 'pending', security: 'pending', human: 'CHANGES' }, true, null],
    [{ code: 'pending', security: 'pending', human: 'CHANGES' }, false, 'CHANGES'],
    [{ code: 'PASS', security: 'pending', human: 'CHANGES' }, true, null],
    [{ code: 'PASS', security: 'invalid', human: 'CHANGES' }, true, 'CHANGES'],
    [{ code: 'PASS', security: 'PASS', human: 'CHANGES' }, true, 'CHANGES'],
    [{ code: 'CHANGES', security: 'pending', human: 'CHANGES' }, true, 'CHANGES'],
    [{ code: 'pending', security: 'pending' }, true, null],
  ] as const)('reads %j at work=%s as %s: the request of the human alone does not decide a round whose reviewers have not all reported', (reviews, isWorking, outcome) => {
    expect(roundOutcome({ n: 1, reviews }, isWorking)).toBe(outcome);
  });

  it('has no outcome for a round that does not exist', () => {
    expect(roundOutcome(undefined)).toBeNull();
  });
});
