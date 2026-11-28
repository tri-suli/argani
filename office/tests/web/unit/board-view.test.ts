import { describe, expect, it } from 'vitest';
import BoardView from '@/board/board-view';
import { formatCount, formatDuration, formatElapsed, pluralize } from '@/board/format';
import { fileName, groupFiles, isMarkdownFile } from '@/board/file-view';
import { sampleAgent, sampleTask, sampleDetail, sampleSnapshot, sampleSummary, sampleTasks } from '../sample-snapshot';

const boardView = new BoardView();

describe('formatting', () => {
  it('formats durations', () => {
    expect([0, 59_999, 125_000, 59 * 60_000, 3_900_000, 7_200_000].map(formatDuration)).toEqual(['0m', '0m', '2m', '59m', '1h05m', '2h00m']);
  });

  it('formats the time since an agent started down to the second', () => {
    expect([-5000, 0, 42_000, 60_000, 125_000, 725_000, 3_599_000, 3_900_000, 7_265_000].map(formatElapsed)).toEqual(['0s', '0s', '42s', '1m 00s', '2m 05s', '12m 05s', '59m 59s', '1h 05m', '2h 01m']);
  });

  it('pluralizes a noun by its count', () => {
    expect([0, 1, 2].map((count) => pluralize(count, 'task'))).toEqual(['0 tasks', '1 task', '2 tasks']);
  });

  it('formats counts', () => {
    expect([0, 999, 1000, 6000, 48_200, 999_949, 999_950, 1_200_000].map(formatCount)).toEqual(['0', '999', '1.0k', '6.0k', '48.2k', '999.9k', '1.0M', '1.2M']);
  });
});

const now = Date.parse('2026-11-24T10:00:10Z');

const snapshotOf = (...tasks: ReturnType<typeof sampleTask>[]) => sampleSnapshot({ projects: [{ name: 'p', tasks }], agents: [] });

describe('board view', () => {
  it('lists project names', () => {
    expect(boardView.projectNames(sampleSnapshot())).toEqual(['demo', 'other']);
  });

  it('groups cards into the five pipeline columns, newest first, by the column of board.json', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), null, now);

    expect(columns.map((column) => [column.step, column.name])).toEqual([['01', 'Intake'], ['02', 'Spec'], ['03', 'Build'], ['04', 'Review'], ['05', 'Approve']]);

    expect(columns.map((column) => column.cards.map((card) => card.task.slug))).toEqual([['add-login'], [], ['fix-export'], ['older'], []]);

    expect(columns.map((column) => column.who)).toEqual(['intake', 'spec-writer', 'builder · verify', 'reviewers', 'approver · merge']);
  });

  it('puts tasks without a timestamp last and orders ties by key', () => {
    const tasks = ['b', 'a', 'dated'].map((slug) => sampleTask({ project: 'p', slug }));

    const dated = [sampleSummary({ project: 'p', slug: 'dated', updatedAt: '2026-01-01T00:00:00Z' })];

    expect(boardView.groupTasksByColumn(snapshotOf(...tasks), dated, null, now)[2].cards.map((card) => card.key)).toEqual(['p/dated', 'p/a', 'p/b']);
  });

  it.each([['Intake'], ['Spec'], ['Build'], ['Review'], ['Approve'], ['Needs human'], ['Done']])('takes the column %s from the task', (column) => {
    expect(boardView.columnOf(sampleTask({ project: 'p', slug: 's', stage: 'whatever', column }))).toBe(column);
  });

  it.each([['Backlog'], [''], ['something-new']])('puts the unknown column "%s" in Needs human', (column) => {
    expect(boardView.columnOf(sampleTask({ project: 'p', slug: 's', column }))).toBe('Needs human');
  });

  it('keeps Needs human and Done tasks out of the pipeline columns', () => {
    const tasks = [sampleTask({ project: 'p', slug: 'asked', column: 'Needs human' }), sampleTask({ project: 'p', slug: 'merged', column: 'Done' }), sampleTask({ project: 'p', slug: 'odd', column: 'Odd' })];

    expect(boardView.groupTasksByColumn(snapshotOf(...tasks), [], null, now).flatMap((column) => column.cards)).toEqual([]);
  });

  it('lists the tasks in Needs human longest wait first, with reason, question, visits and the answer command', () => {
    const history = (ts: string) => [{ ts, stage: 'needs-human', column: 'Needs human', reason: 'manual-verification' }];

    const asked = (slug: string, ts: string | null, overrides = {}) =>
      sampleTask({ project: 'p', slug, column: 'Needs human', reason: 'intake-question', question: `Q ${slug}?`, history: ts ? history(ts) : [], ...overrides });

    const snapshot = snapshotOf(
      asked('recent', '2026-11-24T09:59:00Z'),
      asked('oldest', '2026-11-24T08:00:00Z', { metrics: { manualAcceptanceCriteria: 0, needsHumanCount: 2, needsHumanMilliseconds: 0 }, reason: null, question: null }),
      asked('unknown', null),
      asked('also-unknown', null),
      sampleTask({ project: 'p', slug: 'odd', column: 'Unreadable', question: 'tasks.json is unreadable' }),
      sampleTask({ project: 'p', slug: 'not-waiting', column: 'Build' }),
    );

    const rows = boardView.needsHumanRows(snapshot, null, now);

    expect(rows.map((row) => row.key)).toEqual(['p/oldest', 'p/recent', 'p/also-unknown', 'p/odd', 'p/unknown']);

    expect(rows[0]).toMatchObject({ reason: 'Needs human', waiting: '2h00m', question: null, visits: '2× you', command: '/argani:factory answer oldest <answer>' });

    expect(rows[1]).toMatchObject({ reason: 'intake question', waiting: '1m', question: 'Q recent?', visits: '' });

    expect(rows[3]).toMatchObject({ waiting: '', question: 'tasks.json is unreadable' });
  });

  const entry = (ts: string, column: string, reason: string | null = null) => ({ ts, stage: 'whatever', column, reason });

  it('measures the wait from the first entry of the run in Needs human, not from the last entry', () => {
    const task = sampleTask({
      project: 'p',
      slug: 's',
      column: 'Needs human',
      history: [entry('2026-11-24T09:00:00Z', 'Review'), entry('2026-11-24T10:00:00Z', 'Needs human', 'mr-missing'), entry('2026-11-24T11:55:00Z', 'Needs human', 'merge-missing')],
    });

    expect(boardView.waitedMilliseconds(task, Date.parse('2026-11-24T12:00:00Z'))).toBe(7_200_000);

    expect(boardView.needsHumanRows(snapshotOf(task), null, Date.parse('2026-11-24T12:00:00Z'))[0].waiting).toBe('2h00m');
  });

  it('starts a new wait when the task left Needs human and came back', () => {
    const task = sampleTask({
      project: 'p',
      slug: 's',
      column: 'Needs human',
      history: [entry('2026-11-24T08:00:00Z', 'Needs human'), entry('2026-11-24T09:00:00Z', 'Build'), entry('2026-11-24T11:00:00Z', 'Needs human')],
    });

    expect(boardView.waitedMilliseconds(task, Date.parse('2026-11-24T12:00:00Z'))).toBe(3_600_000);
  });

  it('never measures below zero', () => {
    const future = sampleTask({ project: 'p', slug: 'future', column: 'Needs human', history: [entry('2026-11-24T10:05:00Z', 'Needs human')] });

    expect(boardView.waitedMilliseconds(future, now)).toBe(0);

    expect(boardView.waitedMilliseconds(sampleSnapshot().projects[0].tasks[3], now)).toBe(2_410_000);
  });

  it('knows no wait without history, when the last entry is not in Needs human, or when its date is unreadable', () => {
    expect(boardView.waitedMilliseconds(sampleSnapshot().projects[0].tasks[0], now)).toBeNull();

    const left = sampleTask({ project: 'p', slug: 'left', column: 'Unreadable', history: [entry('2026-11-24T09:00:00Z', 'Needs human'), entry('2026-11-24T09:30:00Z', 'Build')] });

    expect(boardView.waitedMilliseconds(left, now)).toBeNull();

    const garbled = sampleTask({ project: 'p', slug: 'garbled', column: 'Needs human', history: [entry('not a date', 'Needs human')] });

    expect(boardView.waitedMilliseconds(garbled, now)).toBeNull();

    const rows = boardView.needsHumanRows(snapshotOf(left, garbled), null, now);

    expect(rows.map((row) => row.waiting)).toEqual(['', '']);

    expect(boardView.totalTiles(snapshotOf(left, garbled), [], null, now)[1]).toMatchObject({ value: '—', detail: '2 tasks' });
  });

  it('lists the Done tasks newest first as merged or cancelled with the agent time when known', () => {
    const rows = boardView.doneRows(sampleSnapshot(), sampleTasks(), null);

    expect(rows.map((row) => [row.key, row.outcome, row.icon, row.cancelled, row.time])).toEqual([
      ['other/dropped', 'cancelled', 'block', true, ''],
      ['other/ship', 'merged', 'merge', false, '1h05m'],
    ]);

    expect(boardView.doneRows(sampleSnapshot(), sampleTasks(), 'demo')).toEqual([]);
  });

  it('shows a task without a summary in the Done rail without agent time', () => {
    expect(boardView.doneRows(snapshotOf(sampleTask({ project: 'p', slug: 'x', column: 'Done' })), [], null)[0]).toMatchObject({ key: 'p/x', time: '', outcome: 'merged' });
  });

  it('puts Done tasks without a timestamp last, ties by key', () => {
    const tasks = ['c', 'a', 'dated', 'b'].map((slug) => sampleTask({ project: 'p', slug, column: 'Done' }));

    const dated = [sampleSummary({ project: 'p', slug: 'dated', updatedAt: '2026-01-01T00:00:00Z' })];

    expect(boardView.doneRows(snapshotOf(...tasks), dated, null).map((row) => row.key)).toEqual(['p/dated', 'p/a', 'p/b', 'p/c']);
  });

  it('sums the four totals tiles over every project', () => {
    const tiles = boardView.totalTiles(sampleSnapshot(), sampleTasks(), null, now);

    expect(tiles.map((tile) => [tile.id, tile.label, tile.value, tile.detail, tile.tone])).toEqual([
      ['agents', 'Agents working', '1', 'builder', 'active'],
      ['waiting', 'Waiting for you', '40m', '2 tasks', 'human'],
      ['tokens', 'Tokens', '48.2k', 'across 5 open tasks', ''],
      ['manual', 'Manual acceptance criteria', '3', 'to check by hand before merge', ''],
    ]);
  });

  it('counts the tokens of the open tasks only, never those of a Done task', () => {
    const tasks = [sampleTask({ project: 'p', slug: 'open' }), sampleTask({ project: 'p', slug: 'finished', column: 'Done' })];

    const usage = (slug: string, total: number) => sampleSummary({ project: 'p', slug, tokens: { input: 0, output: 0, cacheCreation: 0, cacheRead: 0, total } });

    expect(boardView.totalTiles(snapshotOf(...tasks), [usage('open', 1500), usage('finished', 900_000)], null, now)[2]).toMatchObject({ value: '1.5k', detail: 'across 1 open task' });
  });

  it('follows the project filter in every tile', () => {
    const [agents, waiting, tokens, manual] = boardView.totalTiles(sampleSnapshot(), sampleTasks(), 'other', now);

    expect([agents.value, agents.detail, waiting.value, waiting.detail, tokens.value, tokens.detail, manual.value]).toEqual(['0', '—', '—', '1 task', '0', 'across 1 open task', '1']);
  });

  it('shows dashes and zero when nothing runs, waits or is open', () => {
    const [agents, waiting, tokens] = boardView.totalTiles(snapshotOf(sampleTask({ project: 'p', slug: 'x', column: 'Done' })), [], null, now);

    expect([agents.detail, waiting.value, waiting.detail, tokens.value, tokens.detail, tokens.tone]).toEqual(['—', '—', '0 tasks', '0', 'across 0 open tasks', '']);
  });

  it('names each running agent type once, without its plugin prefix', () => {
    const agents = [sampleAgent, { ...sampleAgent, tool_use_id: 'b' }, { ...sampleAgent, agent_type: 'argani:spec-writer', tool_use_id: 'c' }, { ...sampleAgent, agent_type: 'plain', tool_use_id: 'd' }];

    expect(boardView.totalTiles(sampleSnapshot({ agents }), [], null, now)[0]).toMatchObject({ value: '4', detail: 'builder · spec-writer · plain' });
  });

  it('lists projects with their task count and the tasks waiting for you, All projects first', () => {
    expect(boardView.projectOptions(sampleSnapshot())).toEqual([
      { value: '', label: 'All projects', count: 7, waiting: 2 },
      { value: 'demo', label: 'demo', count: 4, waiting: 1 },
      { value: 'other', label: 'other', count: 3, waiting: 1 },
    ]);
  });

  it('filters the project options by name, ignoring case and surrounding spaces', () => {
    const options = boardView.projectOptions(sampleSnapshot());

    expect(boardView.searchProjectOptions(options, '  OTH ').map((option) => option.label)).toEqual(['other']);

    expect(boardView.searchProjectOptions(options, 'all').map((option) => option.label)).toEqual(['All projects']);

    expect(boardView.searchProjectOptions(options, '').map((option) => option.label)).toEqual(['All projects', 'demo', 'other']);

    expect(boardView.searchProjectOptions(options, 'zzz')).toEqual([]);
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

  it('builds card details from the task summary and the running agent', () => {
    const [, , build, review] = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), null, now);

    const card = build.cards[0];

    expect(card).toMatchObject({ active: true, risk: 'medium', riskIcon: 'warning', mrUrl: 'https://example.test/mr/7', time: '2m', tokens: '48.2k tok' });

    expect(card.agents).toEqual([{ id: 'toolu_1', name: 'builder', elapsed: '10s' }]);

    expect(card.rounds).toEqual([
      { n: 1, label: 'R1', chips: [{ reviewer: 'code', state: 'PASS', className: 'PASS', icon: 'check' }, { reviewer: 'compliance', state: 'pending', className: 'wait', icon: 'hourglass_top' }] },
    ]);

    expect(review.cards[0].rounds[0].chips.map((chip) => [chip.className, chip.icon])).toEqual([['CHANGES', 'priority_high'], ['bad', 'error']]);

    expect(review.cards[0]).toMatchObject({ active: false, agents: [] });
  });

  it('shows every agent running on a task', () => {
    const agents = [sampleAgent, { ...sampleAgent, tool_use_id: 'b', agent_type: 'argani:reviewer', ts: '2026-11-24T09:58:05Z' }];

    const [, , build] = boardView.groupTasksByColumn(sampleSnapshot({ agents }), sampleTasks(), null, now);

    expect(build.cards[0].agents.map((agent) => `${agent.name} ${agent.elapsed}`)).toEqual(['builder 10s', 'reviewer 2m 05s']);
  });

  it('shows no details for a task without summary or usage, and no icon for an unknown risk', () => {
    const [intake] = boardView.groupTasksByColumn(sampleSnapshot(), [sampleSummary({ project: 'demo', slug: 'add-login' })], null, now);

    expect(intake.cards[0]).toMatchObject({ time: '', tokens: '', risk: null, riskIcon: '', mrUrl: null, rounds: [] });

    const [withoutSummary] = boardView.groupTasksByColumn(sampleSnapshot(), [], null, now);

    expect(withoutSummary.cards[0]).toMatchObject({ time: '', tokens: '', rounds: [] });
  });

  it('does not breathe on pending reviews outside Build and Review', () => {
    expect(boardView.chipClassName('pending', false)).toBe('pending');

    expect(boardView.chipClassName('pending', true)).toBe('wait');

    expect(boardView.chipClassName('invalid', true)).toBe('bad');
  });

  it('filters the cards by project', () => {
    const columns = boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), 'other', now);

    expect(columns.flatMap((column) => column.cards)).toEqual([]);

    expect(boardView.groupTasksByColumn(sampleSnapshot(), sampleTasks(), 'demo', now).flatMap((column) => column.cards)).toHaveLength(3);
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
