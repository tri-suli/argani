import { describe, expect, it } from 'vitest';
import BoardView from '@/board/board-view';
import { PIPELINE } from '@/constants/pipeline';
import { formatCount, formatDuration } from '@/board/format';
import { fileName, groupFiles, isMarkdownFile } from '@/board/file-view';
import { sampleAgent, sampleDetail, sampleSnapshot, sampleSummary, sampleTasks } from '../sample-snapshot';

const boardView = new BoardView();

describe('formatting', () => {
  it('formats durations', () => {
    expect([0, 59_999, 125_000, 59 * 60_000, 3_900_000, 7_200_000].map(formatDuration)).toEqual(['0m', '0m', '2m', '59m', '1h05m', '2h00m']);
  });

  it('formats counts', () => {
    expect([0, 999, 1000, 6000, 48_200, 999_949, 999_950, 1_200_000].map(formatCount)).toEqual(['0', '999', '1.0k', '6.0k', '48.2k', '999.9k', '1.0M', '1.2M']);
  });
});

describe('board view', () => {
  it('lists project names', () => {
    expect(boardView.projectNames(sampleSnapshot())).toEqual(['demo', 'other']);
  });

  it('groups cards into the pipeline columns, newest first, ignoring the plugin columns', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), null);

    expect(columns.map((column) => column.name)).toEqual(['Intake', 'Spec', 'Build', 'Review', 'Approve', 'Needs human', 'Done']);

    expect(columns.map((column) => column.cards.map((card) => card.task.slug))).toEqual([['add-login'], [], ['fix-export'], ['older'], [], ['stuck'], ['ship']]);
  });

  it('puts tasks without a timestamp last and orders ties by key', () => {
    const tasks = ['b', 'a', 'dated'].map((slug) => ({ project: 'p', slug, title: slug, stage: 'needs-build', column: 'Backlog', merged: null, next: '-' }));

    const snapshot = sampleSnapshot({ projects: [{ name: 'p', tasks }] });

    const dated = [sampleSummary({ project: 'p', slug: 'dated', updatedAt: '2026-01-01T00:00:00Z' })];

    expect(boardView.groupTasksByColumn(snapshot, dated, null)[2].cards.map((card) => card.key)).toEqual(['p/dated', 'p/a', 'p/b']);
  });

  it.each([
    ['needs-intent-approval', null, 'Intake'],
    ['needs-spec', null, 'Spec'],
    ['needs-spec-approval', null, 'Spec'],
    ['needs-build', null, 'Build'],
    ['needs-rework', null, 'Build'],
    ['needs-review', null, 'Review'],
    ['needs-decision', null, 'Approve'],
    ['needs-mr', null, 'Approve'],
    ['done', null, 'Approve'],
    ['done', false, 'Approve'],
    ['done', true, 'Done'],
    ['escalate', null, 'Needs human'],
    ['error', null, 'Needs human'],
    ['something-new', null, 'Needs human'],
  ])('maps stage %s (merged %s) to %s', (stage, merged, expected) => {
    expect(boardView.columnOf({ project: 'p', slug: 's', title: 't', stage, column: 'Backlog', merged, next: '-' })).toBe(expected);
  });

  it('labels the pipeline columns and tones the last two', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), [], null);

    expect(columns.map((column) => column.who)).toEqual(PIPELINE.map((column) => column.who));

    expect(columns.map((column) => column.who)).toEqual(['intent · you approve', 'spec-writer', 'builder · verify', 'reviewers', 'approver · you merge', 'you', 'merged']);

    expect(columns.map((column) => column.tone)).toEqual(['', '', '', '', '', 'human', 'merged']);
  });

  it('flags the cards whose next step is the human', () => {
    const stages: [string, boolean | null][] = [
      ['needs-intent-approval', null], ['needs-spec', null], ['needs-spec-approval', null], ['needs-build', null], ['needs-review', null],
      ['needs-decision', null], ['done', null], ['done', true], ['escalate', null], ['error', null], ['unknown', null],
      ['needs-mr', null], ['needs-rework', null],
    ];

    const tasks = stages.map(([stage, merged], index) => ({ project: 'p', slug: `t${index}`, title: 't', stage, column: 'Backlog', merged, next: `next ${index}` }));

    const snapshot = sampleSnapshot({ projects: [{ name: 'p', tasks }] });

    const cards = boardView.groupTasksByColumn(snapshot, [], null).flatMap((column) => column.cards);

    const flagged = cards.filter((card) => card.flag !== null).map((card) => card.task.slug).sort();

    expect(flagged).toEqual(['t0', 't10', 't2', 't6', 't8', 't9']);

    expect(cards.find((card) => card.task.slug === 't6')).toMatchObject({ flag: 'your call', hint: 'next 6', dimmed: false });

    expect(cards.find((card) => card.task.slug === 't7')).toMatchObject({ flag: null, hint: null, dimmed: true });
  });

  it('builds card details from the task summary', () => {
    const [, , build, review, , needsHuman, done] = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), null);

    const card = build.cards[0];

    expect(card).toMatchObject({ active: true, risk: 'medium', mrUrl: 'https://example.test/mr/7', time: '2m', tokens: '48.2k tok', flag: null, hint: null, dimmed: false });

    expect(card.rounds).toEqual([
      { n: 1, label: 'R1', chips: [{ reviewer: 'code', state: 'PASS', className: 'PASS' }, { reviewer: 'compliance', state: 'pending', className: 'wait' }] },
    ]);

    expect(review.cards[0].rounds[0].chips.map((chip) => chip.className)).toEqual(['CHANGES', 'bad']);

    expect(done.cards[0]).toMatchObject({ dimmed: true, time: '1h05m', tokens: '1.2M tok', active: false });

    expect(needsHuman.cards[0]).toMatchObject({ flag: 'your call', hint: 'decide the schema', risk: 'high' });
  });

  it('shows no details for a task without summary or usage', () => {
    const [intake] = boardView.groupTasksByColumn(sampleSnapshot(), [sampleSummary({ project: 'demo', slug: 'add-login' })], null);

    expect(intake.cards[0]).toMatchObject({ time: '', tokens: '', risk: null, mrUrl: null, rounds: [] });

    const [withoutSummary] = boardView.groupTasksByColumn(sampleSnapshot(), [], null);

    expect(withoutSummary.cards[0]).toMatchObject({ time: '', tokens: '', rounds: [] });
  });

  it('does not breathe on pending reviews outside Build and Review', () => {
    expect(boardView.chipClassName('pending', false)).toBe('pending');

    expect(boardView.chipClassName('pending', true)).toBe('wait');

    expect(boardView.chipClassName('invalid', true)).toBe('bad');
  });

  it('filters by project and sums tokens', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), 'other');

    expect(columns.flatMap((column) => column.cards.map((card) => card.task.slug))).toEqual(['ship']);

    expect(boardView.totalTokens(sampleTasks())).toBe(1_248_200);
  });

  it('joins agents to tasks on project and slug', () => {
    const tasks = sampleSnapshot().projects[0].tasks;

    const agents = [sampleAgent, { ...sampleAgent, project: 'other' }, { ...sampleAgent, slug: null }];

    expect(boardView.agentsWorkingOn(agents, tasks[1])).toEqual([sampleAgent]);

    expect(boardView.agentsWorkingOn(agents, tasks[0])).toEqual([]);
  });
});

describe('file view', () => {
  it('groups files in order of first appearance', () => {
    const groups = groupFiles(sampleDetail().files);

    expect(groups.map((group) => [group.name, group.files.map((file) => file.path)])).toEqual([
      ['Job', ['spec.md', 'build.diff']],
      ['Round 1', ['review/round-1/review-code.md']],
    ]);

    expect(groupFiles([])).toEqual([]);
  });

  it('names files and detects markdown', () => {
    expect(fileName('review/round-1/review-code.md')).toBe('review-code.md');

    expect(fileName('spec.md')).toBe('spec.md');

    expect([isMarkdownFile('a.md'), isMarkdownFile('A.MD'), isMarkdownFile('a.diff')]).toEqual([true, true, false]);
  });
});
