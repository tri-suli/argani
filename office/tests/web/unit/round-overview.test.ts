import { describe, expect, it } from 'vitest';
import RoundOverview from '@/board/round-overview';
import type { TaskDetail, TaskFile } from '@/types/task';
import { sampleDetail } from '../sample-snapshot';
import sampleMarkdownRenderer from '../sample-markdown-renderer';

const overview = new RoundOverview(sampleMarkdownRenderer());

const CLOSING = '=== END OF REVIEW ===';

const finding = (severity: string, location: string, tail = 'What: w. Why: y. Fix: f.') => `- [${severity}] ${location} - ${tail}`;

const reviewFile = (round: number, name: string, firstLine = 'PASS'): TaskFile => ({ path: `review/round-${round}/review-${name}.md`, group: `Round ${round}`, firstLine, tone: null });

const pathOf = (round: number, name: string) => `review/round-${round}/review-${name}.md`;

const textOf = (...lines: string[]) => [...lines, CLOSING, ''].join('\n');

/** A task in Review with round 1 decided and round 2 as given. */
const detailWith = (overrides: Partial<TaskDetail> = {}): TaskDetail => sampleDetail({
  column: 'Review',
  rounds: [{ n: 1, reviews: { code: 'CHANGES', security: 'PASS' } }],
  models: { reviewers: { code: 'opus', security: 'inherit' } },
  files: [reviewFile(1, 'code', 'CHANGES x'), reviewFile(1, 'security'), { path: 'review/round-1/change.diff', group: 'Round 1', firstLine: 'diff --git', tone: null }, reviewFile(2, 'code')],
  ...overrides,
});

const codeText = textOf('CHANGES the per-commit check corrupts the config', finding('Important', 'a.sh:6'), finding('Nit', 'b.md:2'), finding('Important', 'c.sh:9', 'What: **bold** `code` [link](https://example.test). Why: y. Fix: f.'));

const securityText = textOf('PASS no secret leaks', finding('Nit', 'compose.yaml:12'));

describe('round overview: the options of the dropdown', () => {
  it('lists the rounds of the files in order, each with the outcome of the round', () => {
    const detail = detailWith({
      rounds: [{ n: 1, reviews: { code: 'CHANGES' } }, { n: 2, reviews: { code: 'PASS' } }, { n: 3, reviews: { code: 'pending' } }],
      files: [reviewFile(3, 'code'), reviewFile(1, 'code'), reviewFile(2, 'code')],
    });

    expect(overview.options(detail).map((option) => [option.round, option.title, option.status.label, option.status.icon, option.status.spinning])).toEqual([
      [1, 'Round 1', 'CHANGES', 'error', false],
      [2, 'Round 2', 'PASS', 'check_circle', false],
      [3, 'Round 3', 'RUNNING', 'progress_activity', true],
    ]);
  });

  it('calls an undecided round that is not running undecided, with a plain icon', () => {
    const detail = detailWith({ column: 'Needs human', rounds: [{ n: 1, reviews: { code: 'pending' } }] });

    expect(overview.options(detail)[0].status).toMatchObject({ label: 'UNDECIDED', icon: 'hourglass_top', tone: 'none', spinning: false });
  });

  it('has no option for a task without review files', () => {
    expect(overview.options(detailWith({ files: [] }))).toEqual([]);
  });
});

describe('round overview: a decided round', () => {
  const view = () => overview.build({ detail: detailWith(), round: 1, texts: { [pathOf(1, 'code')]: codeText, [pathOf(1, 'security')]: securityText } });

  it('titles the round and says its outcome with the sentence of the data', () => {
    expect(view()).toMatchObject({ round: 1, title: 'Round 1', status: { label: 'CHANGES', tone: 'warn' }, summary: '1 of 2 reviewers asked for changes · 2 important findings, 2 nits' });
  });

  it('makes a card per reviewer file with its verdict, headline, counts and model', () => {
    expect(view().cards.map((card) => [card.name, card.status.label, card.status.tone, card.headline, card.counts, card.model, card.path, card.isHuman, card.isPending])).toEqual([
      ['code', 'CHANGES', 'warn', 'the per-commit check corrupts the config', '2 important · 1 nit', 'opus', pathOf(1, 'code'), false, false],
      ['security', 'PASS', 'good', 'no secret leaks', '0 important · 1 nit', null, pathOf(1, 'security'), false, false],
    ]);
  });

  it('lists the findings of all reviewers, Important first, in file order within a severity', () => {
    expect(view().findings.map((entry) => [entry.severity, entry.location, entry.reviewer])).toEqual([
      ['important', 'a.sh:6', 'code'],
      ['important', 'c.sh:9', 'code'],
      ['nit', 'b.md:2', 'code'],
      ['nit', 'compose.yaml:12', 'security'],
    ]);

    expect(view().counts).toEqual({ all: 4, important: 2, nit: 2 });
  });

  it('draws What, Why and Fix as labelled parts, with the inline markdown rendered', () => {
    const [, second] = view().findings;

    expect(second.parts.map((part) => [part.kind, part.label, part.isLabelled, part.isFix])).toEqual([['what', 'What', true, false], ['why', 'Why', true, false], ['fix', 'Fix', true, true]]);

    expect(second.parts[0].html).toContain('<strong>bold</strong>');

    expect(second.parts[0].html).toContain('<code>code</code>');

    expect(second.parts[0].html).toContain('href="https://example.test"');

    expect(second.icon).toBe('priority_high');
  });

  it('keeps the same keys for the same findings, so a refresh does not rebuild the cards', () => {
    expect(view().findings.map((entry) => entry.key)).toEqual(view().findings.map((entry) => entry.key));

    expect(new Set(view().findings.map((entry) => entry.key)).size).toBe(4);
  });
});

describe('round overview: states of reviewers', () => {
  const running = (texts: Record<string, string | null>) => overview.build({
    detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'pending', security: 'PASS', compliance: 'pending' } }], files: [reviewFile(1, 'security'), reviewFile(1, 'code', 'PASS')] }),
    round: 1,
    texts,
  });

  it('shows a reviewer that has not reported as running while the round is, without a file link when it has none', () => {
    const view = running({ [pathOf(1, 'security')]: securityText, [pathOf(1, 'code')]: textOf('PASS half written', finding('Important', 'x:1')) });

    expect(view.status).toMatchObject({ label: 'RUNNING', spinning: true });

    expect(view.cards.map((card) => [card.name, card.status.label, card.status.spinning, card.isPending, card.counts, card.path])).toEqual([
      ['code', 'RUNNING', true, true, '', pathOf(1, 'code')],
      ['security', 'PASS', false, false, '0 important · 1 nit', pathOf(1, 'security')],
      ['compliance', 'RUNNING', true, true, '', null],
    ]);

    expect(view.findings.map((entry) => entry.reviewer)).toEqual(['security']);

    expect(view.summary).toBe('Of 3 reviewers: 1 passed, 2 not reported yet · 1 nit');
  });

  it('says not reported rather than running when the round is not at work', () => {
    const view = overview.build({ detail: detailWith({ column: 'Needs human', rounds: [{ n: 1, reviews: { code: 'pending' } }], files: [] }), round: 1, texts: {} });

    expect(view.cards[0].status).toMatchObject({ label: 'NOT REPORTED', spinning: false, tone: 'none' });

    expect(view.cards[0].headline).toBe('Has not reported yet.');
  });

  it('shows an invalid verdict, and keeps the findings of that file', () => {
    const view = overview.build({ detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'invalid' } }], files: [reviewFile(1, 'code', 'oops')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('oops not a verdict', finding('Nit', 'a:1')) } });

    expect(view.cards[0]).toMatchObject({ headline: 'oops not a verdict', counts: '0 important · 1 nit', status: { label: 'INVALID', tone: 'stop' } });

    expect(view.findings).toHaveLength(1);
  });

  it('shows a file that could not be read, keeping the state the task gives', () => {
    const view = overview.build({ detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'CHANGES' } }], files: [reviewFile(1, 'code', 'CHANGES')] }), round: 1, texts: { [pathOf(1, 'code')]: null } });

    expect(view.cards[0]).toMatchObject({ status: { label: 'CHANGES' }, headline: 'This file could not be read.', counts: '', path: pathOf(1, 'code') });

    expect(view.summary).toBe('The reviewer asked for changes · 1 file could not be read');
  });

  it('shows a reviewer the task lists with no file as it is, and a file the task does not list from its own verdict', () => {
    const detail = detailWith({ rounds: [{ n: 1, reviews: { code: 'PASS' } }], files: [reviewFile(1, 'ux')] });

    const view = overview.build({ detail, round: 1, texts: { [pathOf(1, 'ux')]: textOf('CHANGES wrong colour', finding('Important', 'a:1')) } });

    expect(view.cards.map((card) => [card.name, card.status.label, card.headline])).toEqual([['code', 'PASS', ''], ['ux', 'CHANGES', 'wrong colour']]);

    const cutOff = overview.build({ detail, round: 1, texts: { [pathOf(1, 'ux')]: 'CHANGES cut off\n- [Nit] a:1 - What: x.' } });

    expect(cutOff.cards[1]).toMatchObject({ isPending: true, counts: '' });

    const invalid = overview.build({ detail, round: 1, texts: { [pathOf(1, 'ux')]: 'nonsense\n=== END OF REVIEW ===' } });

    expect(invalid.cards[1].status.label).toBe('INVALID');
  });

  it('has no model for a task without models, and a file without any text', () => {
    const view = overview.build({ detail: detailWith({ models: null, files: [reviewFile(1, 'code')] }), round: 1, texts: {} });

    expect(view.cards[0]).toMatchObject({ model: null, headline: 'This file could not be read.' });

    expect(overview.build({ detail: detailWith({ models: {} }), round: 1, texts: {} }).cards[0].model).toBeNull();

    expect(overview.build({ detail: detailWith({ models: { reviewers: { code: 7 } } }), round: 1, texts: {} }).cards[0].model).toBeNull();
  });
});

describe('round overview: the human request', () => {
  const humanText = 'CHANGES Owner decision after APPROVE: remove the sets\n\n- [Important] Remove the prepared sets from src/rector.php.\n  - first\n  - second\n\n' + CLOSING + '\n';

  const view = () => overview.build({
    detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'PASS', human: 'CHANGES' } }], files: [reviewFile(1, 'human', 'CHANGES x'), reviewFile(1, 'code')] }),
    round: 1,
    texts: { [pathOf(1, 'human')]: humanText, [pathOf(1, 'code')]: textOf('PASS fine') },
  });

  it('marks the card and its findings as the human’s and counts the request in the sentence, not as a seat', () => {
    expect(view().cards.map((card) => [card.name, card.isHuman, card.model])).toEqual([['code', false, 'opus'], ['human', true, null]]);

    expect(view().findings[0]).toMatchObject({ reviewer: 'human', isHuman: true, location: null });

    expect(view().summary).toBe('The reviewer passed · 1 important finding · includes a request from the human');

    expect(view().status.label).toBe('CHANGES');
  });

  it('renders the multi-line text of a finding as markdown with its nested list', () => {
    const [part] = view().findings[0].parts;

    expect(part).toMatchObject({ kind: 'text', label: '', isLabelled: false, isFix: false });

    expect(part.html).toContain('<li>first</li>');
  });
});

describe('round overview: a round opened by the request of the human', () => {
  const view = (column: string) => overview.build({
    detail: detailWith({ column, rounds: [{ n: 1, reviews: { code: 'pending', security: 'pending', human: 'CHANGES' } }], files: [reviewFile(1, 'human', 'CHANGES x')] }),
    round: 1,
    texts: { [pathOf(1, 'human')]: textOf('CHANGES owner decision', '- [Important] Remove the sets.') },
  });

  it('is running while the reviewers have not reported, with the reviewers running and the sentence saying so', () => {
    expect(view('Review').status).toMatchObject({ label: 'RUNNING', spinning: true });

    expect(overview.options(detailWith({ column: 'Review', rounds: [{ n: 1, reviews: { code: 'pending', human: 'CHANGES' } }], files: [reviewFile(1, 'human', 'CHANGES x')] }))[0].status.label).toBe('RUNNING');

    expect(view('Review').cards.map((card) => [card.name, card.status.label])).toEqual([['code', 'RUNNING'], ['security', 'RUNNING'], ['human', 'CHANGES']]);

    expect(view('Review').summary).toBe('The reviewers have not reported yet · 1 important finding · includes a request from the human');
  });

  it('is CHANGES once the task is no longer at work', () => {
    expect(view('Needs human').status.label).toBe('CHANGES');

    expect(view('Needs human').cards.map((card) => card.status.label)).toEqual(['NOT REPORTED', 'NOT REPORTED', 'CHANGES']);
  });
});

describe('round overview: hostile and odd files', () => {
  it('sanitizes script and event handlers in every part, and in the headline text it never uses as html', () => {
    const text = textOf('CHANGES <script>alert(1)</script>', finding('Important', '<img src=x onerror=alert(1)>:1', 'What: <script>alert(1)</script><img src=x onerror=alert(2)>. Why: [x](javascript:alert(3)). Fix: <a href="javascript:alert(4)">y</a>.'));

    const view = overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: text } });

    const html = view.findings[0].parts.map((part) => part.html).join('');

    expect(html).not.toContain('<script');

    expect(html).not.toContain('onerror');

    expect(html).not.toContain('javascript:');

    expect(view.cards[0].headline).toBe('<script>alert(1)</script>');
  });

  it('shows every finding of a large round', () => {
    const lines = Array.from({ length: 400 }, (_, index) => finding(index % 2 === 0 ? 'Nit' : 'Important', `f${index}.ts:${index}`));

    const view = overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('CHANGES many', ...lines) } });

    expect(view.findings).toHaveLength(400);

    expect(view.counts).toEqual({ all: 400, important: 200, nit: 200 });

    expect(view.findings[0].severity).toBe('important');

    expect(view.findings[399].severity).toBe('nit');
  });

  it('shows a finding with an undefined severity under its own label, after the nits', () => {
    const text = textOf('CHANGES x', finding('Blocker', 'a:1'), finding('Nit', 'b:1'));

    const view = overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: text } });

    expect(view.findings.map((entry) => [entry.severity, entry.severityLabel, entry.icon])).toEqual([['nit', 'Nit', 'info'], ['other', 'Blocker', 'help']]);

    expect(view.counts).toEqual({ all: 2, important: 0, nit: 1 });

    expect(view.cards[0].counts).toBe('0 important · 1 nit · 1 other');
  });

  it('shows what else a file holds as the notes of that reviewer, rendered, under the findings', () => {
    const text = textOf('PASS x', '## Notes', 'Checked **against** the spec.', '- [Nit]');

    const view = overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: text } });

    expect(view.cards[0].otherNote).toBe('Also holds text that is not a finding: shown below the findings.');

    expect(view.findings[0].parts).toEqual([]);

    expect(view.notes).toHaveLength(1);

    expect(view.notes[0]).toMatchObject({ key: 'code', reviewer: 'code', isHuman: false, title: 'Notes from code' });

    expect(view.notes[0].html).toContain('<strong>Notes</strong>');

    expect(view.notes[0].html).toContain('<strong>against</strong>');

    expect(overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('PASS x', 'one line') } }).notes[0].html).toBe('one line');
  });

  it('shows no notes block for a reviewer that has not reported, or a file without notes, and the notes of the human as the human own', () => {
    const detail = detailWith({ rounds: [{ n: 1, reviews: { code: 'pending', security: 'PASS', human: 'CHANGES' } }], files: [reviewFile(1, 'code', 'PASS'), reviewFile(1, 'security', 'PASS'), reviewFile(1, 'human', 'CHANGES')] });

    const view = overview.build({ detail, round: 1, texts: { [pathOf(1, 'code')]: textOf('PASS x', 'half a note'), [pathOf(1, 'security')]: textOf('PASS ok'), [pathOf(1, 'human')]: textOf('CHANGES why', 'Some words from the owner.') } });

    expect(view.notes.map((notes) => [notes.reviewer, notes.isHuman, notes.title])).toEqual([['human', true, 'Notes from the human']]);
  });

  it('shows the notes only under All', () => {
    const view = overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('PASS x', 'a note') } });

    expect(overview.visibleNotes(view, 'all')).toHaveLength(1);

    expect(overview.visibleNotes(view, 'important')).toEqual([]);

    expect(overview.visibleNotes(view, 'nit')).toEqual([]);
  });

  it('builds a round that has no entry in the task rounds from its files alone', () => {
    const view = overview.build({ detail: detailWith({ column: 'Done', rounds: [], files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('PASS x') } });

    expect(view.cards[0].status.label).toBe('PASS');

    expect(view.status.label).toBe('UNDECIDED');
  });
});

describe('round overview: filter and chips', () => {
  const built = () => overview.build({ detail: detailWith(), round: 1, texts: { [pathOf(1, 'code')]: codeText, [pathOf(1, 'security')]: securityText } });

  it('has a chip per filter with the counts', () => {
    expect(overview.chips(built())).toEqual([{ filter: 'all', label: 'All', count: 4 }, { filter: 'important', label: 'Important', count: 2 }, { filter: 'nit', label: 'Nits', count: 2 }]);
  });

  it('keeps the findings of the filter, the other severity included only under All', () => {
    const text = textOf('CHANGES x', finding('Blocker', 'a:1'), finding('Nit', 'b:1'), finding('Important', 'c:1'));

    const view = overview.build({ detail: detailWith({ files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: text } });

    expect(overview.visible(view, 'all')).toHaveLength(3);

    expect(overview.visible(view, 'important').map((entry) => entry.location)).toEqual(['c:1']);

    expect(overview.visible(view, 'nit').map((entry) => entry.location)).toEqual(['b:1']);
  });

  it('says nothing when there is something to show, and what is missing when there is not', () => {
    expect(overview.emptyMessage(built(), 'all')).toBe('');

    const passing = overview.build({ detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'PASS' } }], files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('PASS x') } });

    expect(overview.emptyMessage(passing, 'all')).toBe('No finding cards in this round.');

    expect(overview.emptyMessage(passing, 'important')).toBe('No important finding in this round.');

    expect(overview.emptyMessage(passing, 'nit')).toBe('No nits in this round.');

    const waiting = overview.build({ detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'pending' } }], files: [] }), round: 1, texts: {} });

    const withNotes = overview.build({ detail: detailWith({ rounds: [{ n: 1, reviews: { code: 'PASS' } }], files: [reviewFile(1, 'code')] }), round: 1, texts: { [pathOf(1, 'code')]: textOf('PASS x', 'a note') } });

    expect(overview.emptyMessage(withNotes, 'all')).toBe('No finding cards in this round. The notes of the reviewers are below.');

    expect(overview.emptyMessage(withNotes, 'nit')).toBe('No nits in this round. The notes of the reviewers are under All.');

    expect(overview.emptyMessage(waiting, 'all')).toBe('No findings yet. This page fills in as each reviewer finishes.');

    expect(overview.emptyMessage(waiting, 'nit')).toBe('No nits in this round yet. Some reviewers have not reported.');

    expect(overview.emptyMessage(waiting, 'important')).toBe('No important finding in this round yet. Some reviewers have not reported.');
  });
});
