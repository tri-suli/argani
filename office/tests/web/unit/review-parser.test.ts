import { describe, expect, it } from 'vitest';
import ReviewParser from '@/board/review-parser';

const parser = new ReviewParser();

const CLOSING = '=== END OF REVIEW ===';

const review = (...lines: string[]) => [...lines, CLOSING, ''].join('\n');

describe('review parser: the verdict line', () => {
  it('reads PASS and CHANGES with the rest of the line as the headline', () => {
    expect(parser.parse(review('PASS no Important finding in the code scope'))).toMatchObject({ verdict: 'PASS', headline: 'no Important finding in the code scope', isClosed: true });

    expect(parser.parse(review('CHANGES the per-commit check corrupts the config'))).toMatchObject({ verdict: 'CHANGES', headline: 'the per-commit check corrupts the config' });
  });

  it('allows a verdict without a reason', () => {
    expect(parser.parse(review('PASS'))).toMatchObject({ verdict: 'PASS', headline: '', findings: [], notes: '' });
  });

  it('keeps a first line that is not a verdict as the headline, with no verdict', () => {
    expect(parser.parse(review('Result: PASS'))).toMatchObject({ verdict: null, headline: 'Result: PASS' });

    expect(parser.parse(review('PASSED all'))).toMatchObject({ verdict: null, headline: 'PASSED all' });
  });

  it('does not mistake the name of an object property for a verdict or a severity', () => {
    expect(parser.parse(review('constructor x', '- [constructor] a.ts:1 - What: a.')).verdict).toBeNull();

    expect(parser.parse(review('PASS', '- [toString] a.ts:1 - What: a.')).findings[0]).toMatchObject({ severity: 'other', severityLabel: 'toString' });
  });

  it('reads an empty file as no verdict, not closed, nothing else', () => {
    expect(parser.parse('')).toEqual({ verdict: null, headline: '', findings: [], notes: '', isClosed: false });
  });

  it('reads a file that is only a verdict line as not closed', () => {
    expect(parser.parse('CHANGES wip')).toEqual({ verdict: 'CHANGES', headline: 'wip', findings: [], notes: '', isClosed: false });
  });

  it('survives a byte order mark and CRLF line endings', () => {
    const text = '\ufeffCHANGES x\r\n- [Nit] a.ts:1 - What: w. Why: y. Fix: f.\r\n=== END OF REVIEW ===\r\n';

    const parsed = parser.parse(text);

    expect(parsed).toMatchObject({ verdict: 'CHANGES', headline: 'x', isClosed: true });

    expect(parsed.findings).toHaveLength(1);

    expect(parsed.findings[0].parts.map((part) => part.text)).toEqual(['w.', 'y.', 'f.']);
  });

  it('is closed only when the closing line is the last non-blank line, whatever surrounds it', () => {
    expect(parser.parse('PASS\n\n  === END OF REVIEW ===  \n\n').isClosed).toBe(true);

    expect(parser.parse('PASS\n=== END OF REVIEW ===\ntrailing').isClosed).toBe(false);
  });
});

describe('review parser: findings in the protocol format', () => {
  it('parses severity, location and the three labelled parts', () => {
    const [finding] = parser.parse(review('CHANGES x', '- [Important] src/auth.py:42 - What: token compared with `==`. Why: timing side channel. Fix: use hmac.compare_digest.')).findings;

    expect(finding).toEqual({
      severity: 'important',
      severityLabel: 'Important',
      location: 'src/auth.py:42',
      parts: [
        { kind: 'what', text: 'token compared with `==`.' },
        { kind: 'why', text: 'timing side channel.' },
        { kind: 'fix', text: 'use hmac.compare_digest.' },
      ],
      isComplete: true,
    });
  });

  it('reads Nit, a line range, an absolute path and a location in words', () => {
    const { findings } = parser.parse(review('PASS', '- [Nit] README.md:7-9 - What: a. Why: b. Fix: c.', '- [Nit] /home/me/build.md:43 - What: a. Why: b. Fix: c.', '- [Nit] (scope of this review) - What: a. Why: b. Fix: none.'));

    expect(findings.map((finding) => [finding.severity, finding.location])).toEqual([['nit', 'README.md:7-9'], ['nit', '/home/me/build.md:43'], ['nit', '(scope of this review)']]);
  });

  it('handles a location without a line, a Windows path with spaces and a wrapped path', () => {
    const { findings } = parser.parse(review('CHANGES', '- [Important] Dockerfile - What: a. Why: b. Fix: c.', '- [Important] C:\\Program Files\\app\\main.cs:12 - What: a. Why: b. Fix: c.', '- [Nit] `src/a b.php`:3 - What: a. Why: b. Fix: c.', '- [Nit] `src/x.php` - What: a.'));

    expect(findings.map((finding) => finding.location)).toEqual(['Dockerfile', 'C:\\Program Files\\app\\main.cs:12', '`src/a b.php`:3', 'src/x.php']);
  });

  it('keeps colons, dashes and a second What inside the text of a part', () => {
    const [finding] = parser.parse(review('CHANGES', '- [Important] a.ts:1 - What: step 1: do x - then y: What: again. Why: because: reasons. Fix: do z: now.')).findings;

    expect(finding.parts).toEqual([
      { kind: 'what', text: 'step 1: do x - then y: What: again.' },
      { kind: 'why', text: 'because: reasons.' },
      { kind: 'fix', text: 'do z: now.' },
    ]);
  });

  it('does not take a label inside a code span, or glued to a word, for a part', () => {
    const [finding] = parser.parse(review('CHANGES', '- [Important] a.ts:1 - What: the string `Fix: x` is wrong and so is `` Why: `y` `` and a `lone tick. Why: it matters, see SomeFix: here. Fix: change it.')).findings;

    expect(finding.parts.map((part) => part.kind)).toEqual(['what', 'why', 'fix']);

    expect(finding.parts[0].text).toBe('the string `Fix: x` is wrong and so is `` Why: `y` `` and a `lone tick.');

    expect(finding.parts[1].text).toBe('it matters, see SomeFix: here.');
  });

  it('keeps the parts in the order of the file and skips a label with nothing after it', () => {
    const [finding] = parser.parse(review('CHANGES', '- [Nit] a.ts:2 - Fix: do it. What: the thing. Why:')).findings;

    expect(finding.parts).toEqual([{ kind: 'fix', text: 'do it.' }, { kind: 'what', text: 'the thing.' }]);

    expect(finding.isComplete).toBe(false);
  });

  it('is complete only with a known severity, a location and What, Why and Fix', () => {
    const complete = (line: string) => parser.parse(review('CHANGES', line)).findings[0].isComplete;

    expect(complete('- [Nit] a.ts:1 - What: a. Why: b. Fix: c.')).toBe(true);

    expect(complete('- [Nit] What: a. Why: b. Fix: c.')).toBe(false);

    expect(complete('- [Nit] a.ts:1 - What: a. Why: b.')).toBe(false);

    expect(complete('- [Blocker] a.ts:1 - What: a. Why: b. Fix: c.')).toBe(false);

    expect(complete('- [Nit] a.ts:1 - note What: a. Why: b. Fix: c.')).toBe(false);
  });
});

describe('review parser: findings that depart from the format', () => {
  it('shows a finding with no location or labels whole as text (a human request)', () => {
    const [finding] = parser.parse(review('CHANGES real-data accuracy', '', '- [Important] Fill `channel`: `offline` for `kedawung_cashier`; `online` only for `indogrosir_online`.')).findings;

    expect(finding).toEqual({ severity: 'important', severityLabel: 'Important', location: null, parts: [{ kind: 'text', text: 'Fill `channel`: `offline` for `kedawung_cashier`; `online` only for `indogrosir_online`.' }], isComplete: false });
  });

  it('reads text before the first label as a location only when a dash closes it', () => {
    expect(parser.parse(review('CHANGES', '- [Nit] see the note - What: a thing.')).findings[0].location).toBe('see the note');

    const second = parser.parse(review('CHANGES', '- [Nit] just words What: a thing.')).findings[0];

    expect(second.location).toBeNull();

    expect(second.parts).toEqual([{ kind: 'text', text: 'just words' }, { kind: 'what', text: 'a thing.' }]);
  });

  it('keeps a severity the protocol does not define, with its own label', () => {
    expect(parser.parse(review('CHANGES', '- [Blocker] a.ts:1 - What: a. Why: b. Fix: c.')).findings[0]).toMatchObject({ severity: 'other', severityLabel: 'Blocker', location: 'a.ts:1' });

    expect(parser.parse(review('CHANGES', '- [ important ] b.ts:2 - What: x.')).findings[0]).toMatchObject({ severity: 'important', severityLabel: 'Important' });
  });

  it('keeps indented continuation lines and nested bullets as part of the finding, de-indented', () => {
    const { findings, notes } = parser.parse(review('CHANGES', '- [Important] Address the round-1 nits:', '    - `extract` exits 1', '    - Catch `json.JSONDecodeError`', '', '    A second paragraph.', '', '- [Nit] b.ts:1 - What: next.'));

    expect(findings).toHaveLength(2);

    expect(findings[0].parts).toEqual([{ kind: 'text', text: 'Address the round-1 nits:\n- `extract` exits 1\n- Catch `json.JSONDecodeError`\n\nA second paragraph.' }]);

    expect(notes).toBe('');
  });

  it('finds labels that sit on continuation lines', () => {
    const [finding] = parser.parse(review('CHANGES', '- [Nit] a.ts:1 - What: first', '  line of what.', '  Why: because.', '  Fix: do it.')).findings;

    expect(finding.parts).toEqual([{ kind: 'what', text: 'first\nline of what.' }, { kind: 'why', text: 'because.' }, { kind: 'fix', text: 'do it.' }]);
  });

  it('accepts other bullet markers', () => {
    expect(parser.parse(review('CHANGES', '* [Nit] a.ts:1 - What: a.', '+ [Nit] b.ts:1 - What: b.')).findings).toHaveLength(2);
  });

  it('keeps every line that is part of no finding as notes, in order, around the findings', () => {
    const parsed = parser.parse(review('CHANGES x', '', '## Summary', '- plain bullet without a severity', '- [Nit] a.ts:1 - What: a.', 'Notes: unindented text after the findings', '', 'Another paragraph', '- [Important] b.ts:2 - What: b.'));

    expect(parsed.findings.map((finding) => finding.location)).toEqual(['a.ts:1', 'b.ts:2']);

    expect(parsed.notes).toBe('## Summary\n- plain bullet without a severity\n\nAnother paragraph');

    expect(parsed.findings[0].parts[0].text).toBe('a.\nNotes: unindented text after the findings');
  });

  it('leaves markup as it is for the renderer to sanitize', () => {
    const [finding] = parser.parse(review('CHANGES', '- [Nit] <b>x</b>.ts:1 - What: <script>alert(1)</script> **bold** [l](javascript:alert(1)). Why: <img src=x onerror=alert(1)>. Fix: `<i>`.')).findings;

    expect(finding.location).toBe('<b>x</b>.ts:1');

    expect(finding.parts.map((part) => part.text)).toEqual(['<script>alert(1)</script> **bold** [l](javascript:alert(1)).', '<img src=x onerror=alert(1)>.', '`<i>`.']);
  });

  it('reads a review-human file: CHANGES, a note finding without location, the closing line', () => {
    const parsed = parser.parse('CHANGES Owner decision after APPROVE of round 2: remove the sets\n\n- [Important] Owner decision after APPROVE: (1) Remove the prepared sets. (2) Add a rule.\n\n=== END OF REVIEW ===\n');

    expect(parsed).toMatchObject({ verdict: 'CHANGES', isClosed: true, notes: '' });

    expect(parsed.findings).toHaveLength(1);

    expect(parsed.findings[0]).toMatchObject({ severity: 'important', location: null });
  });
});
