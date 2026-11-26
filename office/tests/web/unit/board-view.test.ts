import { describe, expect, it } from 'vitest';
import BoardView from '@/board/board-view';
import { PIPELINE } from '@/constants/pipeline';
import { formatCount, formatDuration } from '@/board/format';
import { fileName, groupFiles, isMarkdownFile } from '@/board/file-view';
import { sampleAgent, sampleTask, sampleDetail, sampleSnapshot, sampleSummary, sampleTasks } from '../sample-snapshot';

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

  it('groups cards into the pipeline columns, newest first, by the column of board.json', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), null);

    expect(columns.map((column) => column.name)).toEqual(['Intake', 'Spec', 'Build', 'Review', 'Approve', 'Needs human', 'Done']);

    expect(columns.map((column) => column.cards.map((card) => card.task.slug))).toEqual([['add-login'], [], ['fix-export'], ['older'], [], ['stuck'], ['ship']]);
  });

  it('puts tasks without a timestamp last and orders ties by key', () => {
    const tasks = ['b', 'a', 'dated'].map((slug) => sampleTask({ project: 'p', slug }));

    const snapshot = sampleSnapshot({ projects: [{ name: 'p', tasks }] });

    const dated = [sampleSummary({ project: 'p', slug: 'dated', updatedAt: '2026-01-01T00:00:00Z' })];

    expect(boardView.groupTasksByColumn(snapshot, dated, null)[2].cards.map((card) => card.key)).toEqual(['p/dated', 'p/a', 'p/b']);
  });

  it.each([['Intake'], ['Spec'], ['Build'], ['Review'], ['Approve'], ['Needs human'], ['Done']])('takes the column %s from the task', (column) => {
    expect(boardView.columnOf(sampleTask({ project: 'p', slug: 's', stage: 'whatever', column }))).toBe(column);
  });

  it.each([['Backlog'], [''], ['something-new']])('puts the unknown column "%s" in Needs human', (column) => {
    expect(boardView.columnOf(sampleTask({ project: 'p', slug: 's', column }))).toBe('Needs human');
  });

  it('labels the pipeline columns and tones the last two', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), [], null);

    expect(columns.map((column) => column.who)).toEqual(PIPELINE.map((column) => column.who));

    expect(columns.map((column) => column.who)).toEqual(['intake', 'spec-writer', 'builder · verify', 'reviewers', 'approver · merge', 'you', 'merged']);

    expect(columns.map((column) => column.tone)).toEqual(['', '', '', '', '', 'human', 'merged']);
  });

  it('flags only the cards in Needs human, with the reason as label and the question as hint', () => {
    const tasks = [
      sampleTask({ project: 'p', slug: 'asked', column: 'Needs human', reason: 'manual-verification', question: 'Does it work?', next: 'ignored' }),
      sampleTask({ project: 'p', slug: 'no-reason', column: 'Needs human' }),
      sampleTask({ project: 'p', slug: 'intake', column: 'Intake', stage: 'needs-intent-approval', next: 'approve', reason: 'intake-question', question: 'not shown' }),
      sampleTask({ project: 'p', slug: 'merged', column: 'Done', merged: true }),
    ];

    const cards = boardView.groupTasksByColumn(sampleSnapshot({ projects: [{ name: 'p', tasks }] }), [], null).flatMap((column) => column.cards);

    const byKey = (key: string) => cards.find((card) => card.key === `p/${key}`);

    expect(byKey('asked')).toMatchObject({ flag: 'manual-verification', hint: 'Does it work?', dimmed: false });

    expect(byKey('no-reason')).toMatchObject({ flag: 'Needs human', hint: null });

    expect(byKey('intake')).toMatchObject({ flag: null, hint: null });

    expect(byKey('merged')).toMatchObject({ flag: null, hint: null, dimmed: true });
  });

  it('shows a badge with the number of visits to Needs human once there is one', () => {
    const tasks = [
      sampleTask({ project: 'p', slug: 'twice', metrics: { manualAcceptanceCriteria: 0, needsHumanCount: 2, needsHumanMilliseconds: 0 } }),
      sampleTask({ project: 'p', slug: 'never' }),
    ];

    const cards = boardView.groupTasksByColumn(sampleSnapshot({ projects: [{ name: 'p', tasks }] }), [], null).flatMap((column) => column.cards);

    expect(cards.map((card) => [card.key, card.badge]).sort()).toEqual([['p/never', ''], ['p/twice', '2× you']]);
  });

  it('sums manual criteria and waiting time over the shown project', () => {
    expect(boardView.totalsOf(sampleSnapshot(), null)).toEqual({ manualAcceptanceCriteria: 3, needsHumanMilliseconds: 2_100_000 });

    expect(boardView.totalsOf(sampleSnapshot(), 'other')).toEqual({ manualAcceptanceCriteria: 1, needsHumanMilliseconds: 600_000 });
  });

  it('finds a task by project and slug', () => {
    expect(boardView.findTask(sampleSnapshot(), 'demo', 'stuck')?.title).toBe('Stuck task');

    expect(boardView.findTask(sampleSnapshot(), 'demo', 'missing')).toBeNull();

    expect(boardView.findTask(null, 'demo', 'stuck')).toBeNull();
  });

  it('lists the history rows in order with formatted durations', () => {
    const task = sampleSnapshot().projects[0].tasks[3];

    expect(boardView.historyRows(task)).toEqual([{ column: 'Build', duration: '1h00m' }, { column: 'Needs human', duration: '10m' }, { column: 'Build', duration: '10m' }, { column: 'Needs human', duration: '15m' }]);

    expect(boardView.historyRows(sampleSnapshot().projects[0].tasks[0])).toEqual([]);
  });

  it('builds card details from the task summary', () => {
    const [, , build, review, , needsHuman, done] = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), null);

    const card = build.cards[0];

    expect(card).toMatchObject({ active: true, risk: 'medium', mrUrl: 'https://example.test/mr/7', time: '2m', tokens: '48.2k tok', flag: null, badge: '', hint: null, dimmed: false });

    expect(card.rounds).toEqual([
      { n: 1, label: 'R1', chips: [{ reviewer: 'code', state: 'PASS', className: 'PASS' }, { reviewer: 'compliance', state: 'pending', className: 'wait' }] },
    ]);

    expect(review.cards[0].rounds[0].chips.map((chip) => chip.className)).toEqual(['CHANGES', 'bad']);

    expect(done.cards[0]).toMatchObject({ dimmed: true, time: '1h05m', tokens: '1.2M tok', active: false });

    expect(needsHuman.cards[0]).toMatchObject({ flag: 'manual-verification', badge: '2× you', hint: 'decide the schema', risk: 'high' });
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
