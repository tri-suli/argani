import { describe, expect, it } from 'vitest';
import { agentsWorkingOn, chipClassName, COLUMN_WHO, groupTasksByColumn, projectNames, totalTokens } from '../../../src/board/board-view';
import { formatCount, formatDuration } from '../../../src/board/format';
import { fileName, groupFiles, isMarkdownFile } from '../../../src/board/file-view';
import { sampleAgent, sampleDetail, sampleSnapshot, sampleSummary, sampleTasks } from '../sample-snapshot';

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
    expect(projectNames(sampleSnapshot())).toEqual(['demo', 'other']);
  });

  it('groups cards in column order, newest first, and keeps empty columns', () => {
    const columns = groupTasksByColumn(sampleSnapshot({ columns: ['In progress', 'Design', 'Backlog'] }), sampleTasks(), null);
    expect(columns.map((column) => column.name)).toEqual(['In progress', 'Design', 'Backlog']);
    expect(columns.map((column) => column.cards.map((card) => card.task.slug))).toEqual([['fix-export', 'older'], [], ['add-login']]);
  });

  it('puts tasks without a timestamp last and orders ties by key', () => {
    const tasks = [sampleSummary({ project: 'demo', slug: 'older', updatedAt: '2026-01-01T00:00:00Z' })];
    const columns = groupTasksByColumn(sampleSnapshot({ columns: ['In progress'] }), tasks, null);
    expect(columns[0].cards.map((card) => card.key)).toEqual(['demo/older', 'demo/fix-export']);
    const tied = groupTasksByColumn(sampleSnapshot({ columns: ['In progress'] }), [], null);
    expect(tied[0].cards.map((card) => card.key)).toEqual(['demo/fix-export', 'demo/older']);
  });

  it('labels columns with who works on them and tones the last two', () => {
    const names = Object.keys(COLUMN_WHO);
    const columns = groupTasksByColumn(sampleSnapshot({ columns: [...names, 'Custom'] }), [], null);
    expect(columns.map((column) => column.who)).toEqual([...Object.values(COLUMN_WHO), '']);
    expect(columns.map((column) => column.tone)).toEqual(['', '', '', '', '', 'merged', 'human', '']);
    expect(COLUMN_WHO['Needs human']).toBe('you');
  });

  it('builds card details from the task summary', () => {
    const [, inProgress, done, needsHuman] = groupTasksByColumn(sampleSnapshot(), sampleTasks(), null);
    const card = inProgress.cards[0];
    expect(card).toMatchObject({ active: true, risk: 'medium', mrUrl: 'https://example.test/mr/7', time: '2m', tokens: '48.2k tok', flag: null, hint: null, dimmed: false });
    expect(card.rounds).toEqual([
      { n: 1, label: 'R1', chips: [{ reviewer: 'code', state: 'PASS', className: 'PASS' }, { reviewer: 'compliance', state: 'pending', className: 'wait' }] },
    ]);
    expect(inProgress.cards[1].rounds[0].chips.map((chip) => chip.className)).toEqual(['CHANGES', 'bad']);
    expect(done.cards[0]).toMatchObject({ dimmed: true, time: '1h05m', tokens: '1.2M tok', active: false });
    expect(needsHuman.cards[0]).toMatchObject({ flag: 'your call', hint: 'decide the schema', risk: 'high' });
  });

  it('shows no details for a task without summary or usage', () => {
    const [backlog] = groupTasksByColumn(sampleSnapshot(), [sampleSummary({ project: 'demo', slug: 'add-login' })], null);
    expect(backlog.cards[0]).toMatchObject({ time: '', tokens: '', risk: null, mrUrl: null, rounds: [] });
    const [withoutSummary] = groupTasksByColumn(sampleSnapshot(), [], null);
    expect(withoutSummary.cards[0]).toMatchObject({ time: '', tokens: '', rounds: [] });
  });

  it('does not breathe on pending reviews outside In progress', () => {
    expect(chipClassName('pending', false)).toBe('pending');
    expect(chipClassName('pending', true)).toBe('wait');
    expect(chipClassName('invalid', true)).toBe('bad');
  });

  it('filters by project and sums tokens', () => {
    const columns = groupTasksByColumn(sampleSnapshot(), sampleTasks(), 'other');
    expect(columns.flatMap((column) => column.cards.map((card) => card.task.slug))).toEqual(['ship']);
    expect(totalTokens(sampleTasks())).toBe(1_248_200);
  });

  it('joins agents to tasks on project and slug', () => {
    const tasks = sampleSnapshot().projects[0].tasks;
    const agents = [sampleAgent, { ...sampleAgent, project: 'other' }, { ...sampleAgent, slug: null }];
    expect(agentsWorkingOn(agents, tasks[1])).toEqual([sampleAgent]);
    expect(agentsWorkingOn(agents, tasks[0])).toEqual([]);
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
