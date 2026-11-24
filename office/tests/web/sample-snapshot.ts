import type { BoardAgent, BoardSnapshot } from '../../src/board/types';

export const sampleAgent: BoardAgent = {
  ts: '2026-11-24T10:00:00Z',
  event: 'spawn',
  session_id: 's1',
  agent_type: 'argani:builder',
  tool_use_id: 'toolu_1',
  model: 'sonnet',
  project: 'demo',
  slug: 'fix-export',
  parent_agent_type: null,
  cwd: '/work/demo',
};

export function sampleSnapshot(overrides: Partial<BoardSnapshot> = {}): BoardSnapshot {
  return {
    home: '/home/user/.argani',
    generatedAt: '2026-11-24T10:00:05Z',
    columns: ['Backlog', 'In progress', 'Done'],
    projects: [
      {
        name: 'demo',
        tasks: [
          { project: 'demo', slug: 'add-login', title: 'Add login', stage: 'intent', column: 'Backlog', merged: null, next: 'approve intent' },
          { project: 'demo', slug: 'fix-export', title: 'Fix export', stage: 'spec', column: 'In progress', merged: null, next: 'build' },
        ],
      },
      {
        name: 'other',
        tasks: [{ project: 'other', slug: 'ship', title: 'Ship it', stage: 'done', column: 'Done', merged: true, next: '-' }],
      },
    ],
    agents: [sampleAgent],
    ...overrides,
  };
}
