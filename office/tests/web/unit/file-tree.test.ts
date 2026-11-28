import { describe, expect, it } from 'vitest';
import FileTree from '@/board/file-tree';
import type { TaskFile, TaskRound } from '@/types/task';

const fileTree = new FileTree();

const file = (path: string, firstLine = '', tone: TaskFile['tone'] = null): TaskFile => ({ path, group: /^review\/round-(\d+)\//.exec(path) ? `Round ${/round-(\d+)/.exec(path)![1]}` : 'Job', firstLine, tone });

const files: TaskFile[] = [
  file('intent.md', '# Intent'),
  file('decision.md', 'APPROVE merged', 'good'),
  file('review/round-1/review-code.md', 'CHANGES missing a test', 'warn'),
  file('review/round-1/change.diff', 'diff --git'),
  file('review/round-2/review-code.md', 'PASS ok', 'good'),
  file('review/round-3/review-code.md', 'REVIEWING', null),
  file('review/round-3/change.diff', 'diff --git'),
];

const rounds: TaskRound[] = [{ n: 1, reviews: { code: 'CHANGES' } }, { n: 2, reviews: { code: 'PASS' } }, { n: 3, reviews: { code: 'pending' } }];

const labels = (sections: ReturnType<FileTree['sections']>) => sections.map((section) => [section.name, section.rows.map((row) => row.label)]);

describe('file tree', () => {
  it('lists the job files in a group of their own and the review rounds under Review, each round before its files', () => {
    const sections = fileTree.sections(files, rounds, 'Review', [1, 3]);

    expect(labels(sections)).toEqual([
      ['Job', ['intent.md', 'decision.md']],
      ['Review', ['Round 1', 'review-code.md', 'change.diff', 'Round 2', 'Round 3', 'review-code.md', 'change.diff']],
    ]);
  });

  it('gives a file the icon, tag and tone of its first line, and the diff its own icon', () => {
    const [job, review] = fileTree.sections(files, rounds, 'Review', [1]);

    expect(job.rows.map((row) => [row.icon, row.tone, row.tag])).toEqual([['description', 'none', ''], ['check_circle', 'good', 'APPROVE']]);

    expect(review.rows[1]).toMatchObject({ isRound: false, icon: 'error', tone: 'warn', tag: 'CHANGES', nested: true, path: 'review/round-1/review-code.md', tagTitle: 'CHANGES missing a test' });

    expect(review.rows[2]).toMatchObject({ icon: 'difference', tone: 'none', tag: '' });

    const stopped = fileTree.sections([file('blocked.md', 'ESCALATE no', 'stop')], [], 'Build', [])[0].rows[0];

    expect(stopped).toMatchObject({ icon: 'cancel', tone: 'stop', tag: 'ESCALATE' });
  });

  it('shows the outcome of a round as its own icon and tag, and a running round with a spinner', () => {
    const rows = fileTree.sections(files, rounds, 'Review', [])[1].rows;

    expect(rows.map((row) => [row.isRound, row.label, row.icon, row.tone, row.tag, row.spinning])).toEqual([
      [true, 'Round 1', 'error', 'warn', 'CHANGES', false],
      [true, 'Round 2', 'check_circle', 'good', 'PASS', false],
      [true, 'Round 3', 'progress_activity', 'now', 'running', true],
    ]);
  });

  it('does not call an undecided round running unless the task is at work and it is the latest', () => {
    const undecided: TaskRound[] = [{ n: 1, reviews: { code: 'pending' } }, { n: 2, reviews: { code: 'pending' } }];

    const roundFiles = [file('review/round-1/review-code.md'), file('review/round-2/review-code.md')];

    const tagsOf = (column: string) => fileTree.sections(roundFiles, undecided, column, [])[0].rows.map((row) => [row.tag, row.icon]);

    expect(tagsOf('Review')).toEqual([['', 'description'], ['running', 'progress_activity']]);

    expect(tagsOf('Needs human')).toEqual([['', 'description'], ['', 'description']]);
  });

  it('leaves a round without a summary undecided', () => {
    expect(fileTree.sections(files, [], 'Approve', [])[1].rows.map((row) => row.tag)).toEqual(['', '', '']);
  });

  it('marks a round expanded only when it is in the open list, and hides its files otherwise', () => {
    const rows = fileTree.sections(files, rounds, 'Review', [2])[1].rows;

    expect(rows.filter((row) => row.isRound).map((row) => [row.label, row.expanded])).toEqual([['Round 1', false], ['Round 2', true], ['Round 3', false]]);

    expect(rows.map((row) => row.label)).toEqual(['Round 1', 'Round 2', 'review-code.md', 'Round 3']);
  });

  it('keeps another group that the server names under its own heading, in the order given', () => {
    const extra = [{ ...file('notes.md'), group: 'Notes' }, ...files.slice(0, 1), ...files.slice(2, 3)];

    expect(fileTree.sections(extra, rounds, 'Review', []).map((section) => section.name)).toEqual(['Notes', 'Job', 'Review']);
  });

  it('opens the running round, otherwise the latest, and the round of the selected file', () => {
    expect(fileTree.initialOpenRounds(files, rounds, 'Review', null)).toEqual([3]);

    expect(fileTree.initialOpenRounds(files, rounds, 'Approve', null)).toEqual([3]);

    expect(fileTree.initialOpenRounds(files, rounds, 'Review', 'review/round-1/change.diff')).toEqual([1, 3]);

    expect(fileTree.initialOpenRounds(files, rounds, 'Review', 'review/round-3/change.diff')).toEqual([3]);

    expect(fileTree.initialOpenRounds(files, rounds, 'Review', 'intent.md')).toEqual([3]);

    expect(fileTree.initialOpenRounds([file('intent.md')], [], 'Build', 'intent.md')).toEqual([]);
  });

  it('treats the latest round as running when the task is at work and the summary does not list it yet', () => {
    const open = fileTree.initialOpenRounds(files, [{ n: 1, reviews: { code: 'pending' } }], 'Review', null);

    expect(open).toEqual([3]);
  });

  it('adds and removes a round from the open list without touching the others', () => {
    expect(fileTree.toggled([1, 3], 2)).toEqual([1, 2, 3]);

    expect(fileTree.toggled([1, 2, 3], 2)).toEqual([1, 3]);
  });

  it('adds the round of a file to the open list, once', () => {
    expect(fileTree.withRoundOf([3], 'review/round-1/change.diff', files)).toEqual([1, 3]);

    expect(fileTree.withRoundOf([1, 3], 'review/round-1/change.diff', files)).toEqual([1, 3]);

    expect(fileTree.withRoundOf([3], 'intent.md', files)).toEqual([3]);

    expect(fileTree.withRoundOf([3], 'gone.md', files)).toEqual([3]);
  });

  it('names the tone of a row for screen readers', () => {
    const [job, review] = fileTree.sections(files, rounds, 'Review', [1]);

    expect(job.rows.map((row) => row.toneLabel)).toEqual(['', 'passed']);

    expect(review.rows.slice(0, 3).map((row) => row.toneLabel)).toEqual(['changes requested', 'changes requested', '']);

    expect(fileTree.sections(files, rounds, 'Review', [])[1].rows.map((row) => row.toneLabel)).toEqual(['changes requested', 'passed', 'running']);
  });

  it('names the round numbers of the files, and the running round when there is one', () => {
    expect(fileTree.roundNumbers(files)).toEqual([1, 2, 3]);

    expect(fileTree.roundNumbers([file('intent.md')])).toEqual([]);

    expect(fileTree.runningRound(files, rounds, 'Review')).toBe(3);

    expect(fileTree.runningRound(files, rounds, 'Approve')).toBeNull();

    expect(fileTree.runningRound([file('intent.md')], [], 'Review')).toBeNull();
  });
});
