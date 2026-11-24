import { describe, expect, it } from 'vitest';
import { agentsWorkingOn, groupTasksByColumn, projectNames } from '../../../src/board/board-view';
import { sampleAgent, sampleSnapshot } from '../sample-snapshot';

describe('board view', () => {
  it('lists project names', () => {
    expect(projectNames(sampleSnapshot())).toEqual(['demo', 'other']);
  });

  it('groups tasks in column order and keeps empty columns', () => {
    const snapshot = sampleSnapshot({ columns: ['Done', 'Design', 'Backlog'] });
    const columns = groupTasksByColumn(snapshot, null);
    expect(columns.map((column) => column.name)).toEqual(['Done', 'Design', 'Backlog']);
    expect(columns.map((column) => column.tasks.map((task) => task.slug))).toEqual([['ship'], [], ['add-login']]);
  });

  it('filters by project', () => {
    const columns = groupTasksByColumn(sampleSnapshot(), 'other');
    expect(columns.flatMap((column) => column.tasks.map((task) => task.slug))).toEqual(['ship']);
  });

  it('joins agents to tasks on project and slug', () => {
    const tasks = sampleSnapshot().projects[0].tasks;
    const otherProjectAgent = { ...sampleAgent, project: 'other' };
    const unassignedAgent = { ...sampleAgent, slug: null };
    const agents = [sampleAgent, otherProjectAgent, unassignedAgent];
    expect(agentsWorkingOn(agents, tasks[1])).toEqual([sampleAgent]);
    expect(agentsWorkingOn(agents, tasks[0])).toEqual([]);
  });
});
