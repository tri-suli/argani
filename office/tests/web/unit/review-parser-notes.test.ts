import { describe, expect, it } from 'vitest';
import ReviewParser from '@/board/review-parser';
import type { ParsedReview } from '@/types/review-file';

const parser = new ReviewParser();

const CLOSING = '=== END OF REVIEW ===';

const review = (...lines: string[]) => [...lines, CLOSING, ''].join('\n');

const LABELS: Record<string, string> = { what: 'What', why: 'Why', fix: 'Fix', text: '' };

const wordsOf = (text: string) => (text.match(/[\p{L}\p{N}_]+/gu) ?? []).map((word) => word.toLowerCase()).sort();

/** Every word of a file that the overview shows: the verdict and headline, the finding cards, the notes. */
const shownWords = (parsed: ParsedReview) => wordsOf([parsed.verdict ?? '', parsed.headline, parsed.notes, ...parsed.findings.flatMap((finding) => [finding.severityLabel, finding.location ?? '', ...finding.parts.flatMap((part) => [LABELS[part.kind], part.text])])].join(' '));

/** The words of a file as it was written, without the closing line and the markers of its list items. */
const writtenWords = (text: string) => wordsOf(text.split(/\r?\n/).filter((line) => line.trim() !== CLOSING).map((line) => line.replace(/^\s*(?:[-*+]|\d+[.)])\s+/, '')).join('\n'));

const SAMPLES: Record<string, string> = {
  protocol: review('CHANGES the check corrupts the config', '- [Important] src/auth.py:42 - What: token compared with `==`. Why: timing side channel. Fix: use hmac.compare_digest.', '- [Nit] README.md:7 - What: typo. Why: careless. Fix: fix it.'),
  trailingNotes: review('PASS no Important finding', '- [Nit] build.md:43 - What: stale line. Why: record differs. Fix: update it.', 'Notes: `src/AGENTS.md` and `src/CLAUDE.md` not committed, `mbstring` and `HOME=/tmp` are each recorded with their own commits and reasons.'),
  checkedAgainst: review('PASS the diff matches the requirements', '- [Nit] a.rb:1 - What: x. Why: y. Fix: z.', '', 'Checked against the requirements file in the diff itself: layout, the nginx root, workspaces and `cacheDir`, eslint exact pins, the eight compose services.'),
  lazy: review('CHANGES x', '- [Important] a.py:1 - What: foo', 'bar. Why: w. Fix: f.', '', 'a loose paragraph', '- [Nit] b.py:2 - What: n. Why: m. Fix: l.'),
  ordered: review('CHANGES x', '1. [Important] a.py:1 - What: one. Why: two. Fix: three.', '2) [Nit] b.py:2 - What: four. Why: five. Fix: six.'),
  fenced: review('CHANGES x', '- [Important] a.sh:1 - What: the script breaks:', '```sh', 'set -e', '', '- [Nit] this is code, not a finding', '```', 'Why: it fails. Fix: add the guard.', '- [Nit] b.sh:2 - What: next. Why: n. Fix: f.'),
  notesFence: review('PASS x', '## Notes', '', '~~~', '- [Nit] inside a fence', '~~~', 'after the fence'),
  human: 'CHANGES Owner decision: remove the sets\n\n- [Important] Remove the prepared sets.\n  - first\n  - second\n\n- [Important] Add a rule.\n\n=== END OF REVIEW ===\n',
  crlf: '﻿CHANGES x\r\n- [Nit] a.ts:1 - What: w. Why: y. Fix: f.\r\nNotes: tail\r\n=== END OF REVIEW ===\r\n',
  hostile: review('CHANGES <img src=x onerror=1>', '- [Blocker] <b>x</b>.ts:1 - What: <script>alert(1)</script> [l](javascript:alert(1)). Why: y. Fix: z.', '# A heading', '<h1 id="x">raw</h1>'),
  onlyVerdict: 'CHANGES wip',
  empty: '',
};

describe('review parser: nothing a file says is lost', () => {
  it.each(Object.keys(SAMPLES))('shows every word of the %s sample', (name) => {
    expect(shownWords(parser.parse(SAMPLES[name]))).toEqual(writtenWords(SAMPLES[name]));
  });
});

describe('review parser: lazy continuation, fences, ordered findings and notes', () => {
  it('keeps a line that directly follows a bullet in that finding, so its Why and Fix are found', () => {
    const [finding] = parser.parse(SAMPLES.lazy).findings;

    expect(finding.parts).toEqual([{ kind: 'what', text: 'foo\nbar.' }, { kind: 'why', text: 'w.' }, { kind: 'fix', text: 'f.' }]);

    expect(finding.isComplete).toBe(true);
  });

  it('ends a finding at a blank line, a heading, another bullet or a quote, and keeps what follows as notes', () => {
    expect(parser.parse(SAMPLES.lazy).notes).toBe('a loose paragraph');

    expect(parser.parse(review('CHANGES x', '- [Nit] a:1 - What: x.', '## Heading', 'tail')).notes).toBe('## Heading\ntail');

    expect(parser.parse(review('CHANGES x', '- [Nit] a:1 - What: x.', '- plain bullet')).notes).toBe('- plain bullet');

    expect(parser.parse(review('CHANGES x', '- [Nit] a:1 - What: x.', '> a quote')).notes).toBe('> a quote');

    expect(parser.parse(review('CHANGES x', '- [Nit] a:1 - What: x.', '---')).notes).toBe('---');

    expect(parser.parse(review('CHANGES x', '- [Nit] a:1 - What: x.', '1. numbered')).notes).toBe('1. numbered');
  });

  it('puts a Notes line that closes the file straight after the last bullet into that finding, and keeps it whole', () => {
    const [finding] = parser.parse(SAMPLES.trailingNotes).findings;

    expect(finding.parts[2].text).toContain('Notes: `src/AGENTS.md`');

    expect(parser.parse(SAMPLES.trailingNotes).notes).toBe('');
  });

  it('shows a paragraph after a blank line as notes', () => {
    expect(parser.parse(SAMPLES.checkedAgainst).notes).toBe('Checked against the requirements file in the diff itself: layout, the nginx root, workspaces and `cacheDir`, eslint exact pins, the eight compose services.');
  });

  it('keeps a fenced block that starts at column 0 after a bullet whole, blank lines and bullet-like lines included', () => {
    const { findings, notes } = parser.parse(SAMPLES.fenced);

    expect(findings).toHaveLength(2);

    expect(findings[0].parts[0].text).toBe('the script breaks:\n```sh\nset -e\n\n- [Nit] this is code, not a finding\n```');

    expect(findings[0].parts.map((part) => part.kind)).toEqual(['what', 'why', 'fix']);

    expect(notes).toBe('');
  });

  it('keeps a fenced block among the notes whole, with the notes around it', () => {
    expect(parser.parse(SAMPLES.notesFence)).toMatchObject({ findings: [], notes: '## Notes\n\n~~~\n- [Nit] inside a fence\n~~~\nafter the fence' });
  });

  it('reads findings written as ordered list items', () => {
    const { findings } = parser.parse(SAMPLES.ordered);

    expect(findings.map((finding) => [finding.severity, finding.location, finding.isComplete])).toEqual([['important', 'a.py:1', true], ['nit', 'b.py:2', true]]);
  });

  it('separates the notes before and after a finding with a blank line', () => {
    expect(parser.parse(review('PASS x', 'before', '- [Nit] a:1 - What: x.', '', 'after', '', '', 'later')).notes).toBe('before\n\nafter\n\nlater');
  });

  it('has no notes when the file holds only a verdict, findings and the closing line', () => {
    expect(parser.parse(SAMPLES.protocol).notes).toBe('');

    expect(parser.parse('').notes).toBe('');
  });
});
