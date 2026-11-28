import { describe, expect, it } from 'vitest';
import HistorySteps from '@/board/history-steps';
import type { BoardTask, HistoryEntry } from '@/types/board';
import type { TaskRound } from '@/types/task';
import { sampleSummary, sampleTask } from '../sample-snapshot';

const historySteps = new HistorySteps();

const minute = 60_000;

const at = (minutes: number) => new Date(Date.UTC(2026, 10, 24, 8, minutes)).toISOString().replace('.000Z', 'Z');

const now = Date.UTC(2026, 10, 24, 9, 0);

/** A task whose history entries are (column, minute they started[, reason]); each lasts until the next, the last until `until`. */
function taskThrough(entries: [string, number, string?][], until = 60, overrides: Partial<BoardTask> = {}): BoardTask {
  const history: HistoryEntry[] = entries.map(([column, minutes, reason]) => ({ ts: at(minutes), stage: 'stage', column, reason: reason ?? null }));

  const durations = entries.map(([column, minutes], index) => ({ column, milliseconds: ((entries[index + 1]?.[1] ?? until) - minutes) * minute }));

  return sampleTask({ project: 'demo', slug: 'task', column: entries.at(-1)![0], history, durations, ...overrides });
}

const summaryWith = (rounds: TaskRound[]) => sampleSummary({ project: 'demo', slug: 'task', rounds });

const round = (n: number, reviews: TaskRound['reviews']): TaskRound => ({ n, reviews });

describe('history steps', () => {
  it('has no step for a task without history', () => {
    expect(historySteps.derive(sampleTask({ project: 'demo', slug: 'task' }), null, now)).toEqual([]);
  });

  it('numbers the steps oldest first, with the time each stayed, and marks the last one of an open task as now', () => {
    const task = taskThrough([['Intake', 0], ['Spec', 4], ['Build', 7]], 48);

    expect(historySteps.derive(task, null, now)).toEqual([
      { number: '1', name: 'Intake', kind: 'agent', note: '4m' },
      { number: '2', name: 'Spec', kind: 'agent', note: '3m' },
      { number: '3', name: 'Build', kind: 'now', note: 'running · 53m 00s' },
    ]);
  });

  it('merges consecutive entries of the same column into one step', () => {
    const task = taskThrough([['Intake', 0], ['Intake', 3], ['Spec', 10]], 11);

    const steps = historySteps.derive(task, null, now);

    expect(steps.map((step) => [step.name, step.note])).toEqual([['Intake', '10m'], ['Spec', 'running · 50m 00s']]);
  });

  it('shows a wait for the human with its reason in words, and keeps the first reason when a later entry has none', () => {
    const task = taskThrough([['Intake', 0], ['Needs human', 4, 'intake-question'], ['Needs human', 6], ['Intake', 9], ['Build', 10]]);

    expect(historySteps.derive(task, null, now).slice(0, 2)).toEqual([
      { number: '1', name: 'Intake', kind: 'agent', note: '4m' },
      { number: '2', name: 'Needs human', kind: 'human', note: '5m · intake question' },
    ]);
  });

  it('shows a wait without a reason as the duration only', () => {
    const task = taskThrough([['Needs human', 0], ['Build', 5]], 6);

    expect(historySteps.derive(task, null, now)[0]).toEqual({ number: '1', name: 'Needs human', kind: 'human', note: '5m' });
  });

  it('keeps a task that is waiting for the human right now as a wait, with the ticking time, not as running', () => {
    const task = taskThrough([['Build', 0], ['Needs human', 30, 'manual-verification']], 40);

    expect(historySteps.derive(task, null, now).at(-1)).toEqual({ number: '2', name: 'Needs human', kind: 'human', note: '30m 00s · manual verification' });
  });

  it('maps the n-th visit to Review onto review round n: changes asked, passed, or no outcome', () => {
    const task = taskThrough([['Build', 0], ['Review', 10], ['Build', 15], ['Review', 25], ['Build', 30], ['Review', 40], ['Approve', 45]]);

    const summary = summaryWith([round(1, { code: 'PASS', docs: 'CHANGES' }), round(2, { code: 'PASS', docs: 'PASS' }), round(3, { code: 'PASS', docs: 'pending' })]);

    const steps = historySteps.derive(task, summary, now);

    expect(steps.filter((step) => step.name.startsWith('Review')).map((step) => [step.name, step.kind, step.note])).toEqual([
      ['Review R1', 'changes', '5m · changes asked'],
      ['Review R2', 'pass', '5m · passed'],
      ['Review R3', 'agent', '5m'],
    ]);
  });

  it('gives no Review step an outcome when the visits to Review outnumber the rounds (an interrupted review keeps its round)', () => {
    const task = taskThrough([['Review', 0], ['Needs human', 5, 'stuck'], ['Review', 8], ['Approve', 12]]);

    const steps = historySteps.derive(task, summaryWith([round(1, { code: 'CHANGES' })]), now);

    expect(steps.filter((step) => step.name.startsWith('Review')).map((step) => [step.name, step.kind, step.note])).toEqual([
      ['Review', 'agent', '5m'],
      ['Review', 'agent', '4m'],
    ]);
  });

  it('gives no Review step an outcome when there are more rounds than visits, or no summary at all', () => {
    const task = taskThrough([['Review', 0], ['Approve', 5]]);

    const rounds = summaryWith([round(1, { code: 'CHANGES' }), round(2, { code: 'PASS' })]);

    expect(historySteps.derive(task, rounds, now)[0]).toMatchObject({ name: 'Review', kind: 'agent', note: '5m' });

    expect(historySteps.derive(task, null, now)[0]).toMatchObject({ name: 'Review', kind: 'agent', note: '5m' });
  });

  it('does not call a round with no review passed', () => {
    const task = taskThrough([['Review', 0], ['Approve', 5]]);

    expect(historySteps.derive(task, summaryWith([round(1, {})]), now)[0]).toMatchObject({ name: 'Review R1', kind: 'agent', note: '5m' });
  });

  it('shows the running Review round as now, without an outcome', () => {
    const task = taskThrough([['Build', 0], ['Review', 40]], 46);

    const steps = historySteps.derive(task, summaryWith([round(1, { code: 'pending' })]), now);

    expect(steps.at(-1)).toEqual({ number: '2', name: 'Review R1', kind: 'now', note: 'running · 20m 00s' });
  });

  it('ends a Done task with its outcome and no running step, merged or cancelled', () => {
    const merged = taskThrough([['Approve', 0], ['Done', 5]], 60, { column: 'Done', stage: 'done', merged: true });

    expect(historySteps.derive(merged, null, now)).toEqual([
      { number: '1', name: 'Approve', kind: 'agent', note: '5m' },
      { number: '2', name: 'Done', kind: 'pass', note: 'merged' },
    ]);

    const cancelled = taskThrough([['Intake', 0], ['Done', 5]], 60, { column: 'Done', stage: 'cancelled', merged: false });

    expect(historySteps.derive(cancelled, null, now).at(-1)).toEqual({ number: '2', name: 'Done', kind: 'cancelled', note: 'cancelled' });
  });

  it('keeps an unknown column under its own name as an agent step', () => {
    const task = taskThrough([['Unreadable', 0], ['Build', 5]]);

    expect(historySteps.derive(task, null, now)[0]).toEqual({ number: '1', name: 'Unreadable', kind: 'agent', note: '5m' });
  });

  it('never prints NaN: a bad timestamp falls back to the recorded duration, and no duration to a bare "running"', () => {
    const task = taskThrough([['Build', 0]], 12);

    task.history[0].ts = 'yesterday-ish';

    expect(historySteps.derive(task, null, now)[0].note).toBe('running · 12m');

    task.durations[0].milliseconds = Number.NaN;

    expect(historySteps.derive(task, null, now)[0].note).toBe('running');

    const missing = taskThrough([['Intake', 0], ['Build', 5]]);

    missing.durations = [];

    expect(historySteps.derive(missing, null, now).map((step) => step.note)).toEqual(['0m', 'running · 55m 00s']);
  });

  it('shows a clock that is behind the start of the step as zero elapsed', () => {
    const task = taskThrough([['Build', 30]], 40);

    expect(historySteps.derive(task, null, Date.UTC(2026, 10, 24, 8, 0))[0].note).toBe('running · 0s');
  });

  it('takes the reason from a later entry of the same wait when the first has none', () => {
    const task = taskThrough([['Needs human', 0], ['Needs human', 2, 'merge-failed'], ['Build', 5]]);

    expect(historySteps.derive(task, null, now)[0].note).toBe('5m · merge failed');
  });

  it('does not run a step now for a done task or a last entry in Done, whatever the other says', () => {
    const doneTask = taskThrough([['Build', 0], ['Approve', 5]], 60, { column: 'Done', stage: 'done' });

    expect(historySteps.derive(doneTask, null, now).at(-1)).toMatchObject({ name: 'Approve', kind: 'agent', note: '55m' });

    const staleTask = taskThrough([['Build', 0], ['Done', 5]], 60, { column: 'Build', stage: 'done' });

    expect(historySteps.derive(staleTask, null, now).at(-1)).toMatchObject({ name: 'Done', note: 'merged' });
  });

  it('falls back to the recorded wait when the start of a wait cannot be read', () => {
    const task = taskThrough([['Needs human', 0]], 7);

    task.history[0].ts = 'garbled';

    expect(historySteps.derive(task, null, now)[0].note).toBe('7m');

    task.durations[0].milliseconds = 0;

    expect(historySteps.derive(task, null, now)[0].note).toBe('0m');
  });

  it('shows the latest reason on the wait that is still going on, and the first one on a past wait', () => {
    const current = taskThrough([['Build', 0], ['Needs human', 30, 'manual-verification'], ['Needs human', 35, 'merge-failed']], 40);

    expect(historySteps.derive(current, null, now).at(-1)?.note).toBe('30m 00s · merge failed');

    const past = taskThrough([['Needs human', 0, 'manual-verification'], ['Needs human', 2, 'merge-failed'], ['Build', 5]], 40);

    expect(historySteps.derive(past, null, now)[0].note).toBe('5m · manual verification');
  });
});
