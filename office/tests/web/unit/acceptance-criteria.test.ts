import { describe, expect, it } from 'vitest';
import AcceptanceCriteria from '@/board/acceptance-criteria';

const criteria = new AcceptanceCriteria();

describe('acceptance criteria', () => {
  it('reads the number, the claim and the verification of the plugin format', () => {
    expect(criteria.parse('1. [ ] `compose.yaml` defines the services — verify: `docker compose config --services`')).toEqual({
      number: 1,
      claim: '`compose.yaml` defines the services',
      verify: '`docker compose config --services`',
      manual: false,
      checked: false,
    });
  });

  it('accepts a ticked box, which it reports, and a multi-digit number', () => {
    expect(criteria.parse('12. [x] done — verify: npm test')).toMatchObject({ number: 12, claim: 'done', verify: 'npm test', checked: true });

    expect(criteria.parse('3. [X] done — verify: npm test')).toMatchObject({ checked: true });

    expect(criteria.parse('3. [ ] done — verify: npm test')).toMatchObject({ checked: false });
  });

  it('splits at the last " — verify: " like artifact_check.py does', () => {
    expect(criteria.parse('2. [ ] says " — verify: " in prose — verify: make check')).toMatchObject({ claim: 'says " — verify: " in prose', verify: 'make check' });
  });

  it('marks a manual verification and drops the prefix', () => {
    expect(criteria.parse('4. [ ] looks right — verify: manual: open the page')).toMatchObject({ manual: true, verify: 'open the page' });

    expect(criteria.parse('4. [ ] looks right — verify: `manual: open the page`')).toMatchObject({ manual: true, verify: 'open the page' });

    expect(criteria.parse('4. [ ] looks right — verify: Manual:   open the page')).toMatchObject({ manual: true, verify: 'open the page' });
  });

  it('does not call a command that mentions manual a manual criterion', () => {
    expect(criteria.parse('5. [ ] x — verify: `grep manual: docs`')).toMatchObject({ manual: false });
  });

  it.each([
    '- [ ] bullet — verify: npm test',
    '1. [ ] no verification at all',
    '1. claim — verify: no checkbox',
    '1. [ ] empty — verify: ',
    '- AC-1: old format — verify: x',
    '',
  ])('returns null for %j', (line) => {
    expect(criteria.parse(line)).toBeNull();
  });
});
