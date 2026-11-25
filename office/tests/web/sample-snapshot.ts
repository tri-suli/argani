import type { BoardAgent, BoardSnapshot } from '@/types/board';
import type { TaskClient } from '@/types/client';
import type { TaskDetail, TaskSummary } from '@/types/task';

const sampleAgent: BoardAgent = {
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

function sampleSnapshot(overrides: Partial<BoardSnapshot> = {}): BoardSnapshot {
  return {
    home: '/home/user/.argani',
    generatedAt: '2026-11-24T10:00:05Z',
    columns: ['Backlog', 'In progress', 'Done', 'Needs human'], // plugin columns, ignored by the office
    projects: [
      {
        name: 'demo',
        tasks: [
          { project: 'demo', slug: 'add-login', title: 'Add login', stage: 'needs-intent-approval', column: 'Backlog', merged: null, next: 'approve intent' },
          { project: 'demo', slug: 'fix-export', title: 'Fix export', stage: 'needs-build', column: 'In progress', merged: null, next: 'build' },
          { project: 'demo', slug: 'older', title: 'Older work', stage: 'needs-review', column: 'In progress', merged: null, next: 'build' },
          { project: 'demo', slug: 'stuck', title: 'Stuck task', stage: 'escalate', column: 'Needs human', merged: null, next: 'decide the schema' },
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

const noTokens = { input: 0, output: 0, cacheCreation: 0, cacheRead: 0, total: 0 };

function sampleSummary(overrides: Partial<TaskSummary> & Pick<TaskSummary, 'project' | 'slug'>): TaskSummary {
  return { stage: 'build', risk: null, round: 0, rounds: [], mrUrl: null, updatedAt: null, agentMilliseconds: 0, tokens: noTokens, ...overrides };
}

function sampleTasks(): TaskSummary[] {
  return [
    sampleSummary({
      project: 'demo',
      slug: 'fix-export',
      risk: 'medium',
      round: 1,
      rounds: [{ n: 1, reviews: { code: 'PASS', compliance: 'pending' } }],
      mrUrl: 'https://example.test/mr/7',
      updatedAt: '2026-11-24T09:00:00Z',
      agentMilliseconds: 125000,
      tokens: { input: 1, output: 1, cacheCreation: 0, cacheRead: 0, total: 48200 },
    }),
    sampleSummary({ project: 'demo', slug: 'older', updatedAt: '2026-11-23T09:00:00Z', rounds: [{ n: 1, reviews: { code: 'CHANGES', compliance: 'invalid' } }] }),
    sampleSummary({ project: 'demo', slug: 'stuck', risk: 'high', updatedAt: '2026-11-24T08:00:00Z' }),
    sampleSummary({ project: 'other', slug: 'ship', risk: 'low', updatedAt: '2026-11-20T08:00:00Z', agentMilliseconds: 3900000, tokens: { ...noTokens, total: 1_200_000 } }),
  ];
}

function sampleDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    ...sampleSummary({ project: 'demo', slug: 'fix-export', risk: 'medium', round: 1, mrUrl: 'https://example.test/mr/7', agentMilliseconds: 125000, tokens: { ...noTokens, total: 6000 } }),
    stage: 'build',
    next: 'review',
    column: 'In progress',
    reviewers: ['code'],
    models: {},
    decision: { exists: false, complete: false, verdict: null },
    files: [
      { path: 'spec.md', group: 'Job', firstLine: '# Spec', tone: null },
      { path: 'build.diff', group: 'Job', firstLine: 'diff --git', tone: null },
      { path: 'review/round-1/review-code.md', group: 'Round 1', firstLine: 'PASS ok', tone: 'good' },
    ],
    ...overrides,
  };
}

const sampleFileTexts: Record<string, string> = {
  'spec.md': '# Spec\n\nHello **world** <script>alert(1)</script>',
  'build.diff': '+added line\n-removed line\n',
  'review/round-1/review-code.md': 'PASS ok\n\n## Summary\n- all good\n\n## Details\nmore',
};

class FakeTaskClient implements TaskClient {
  detail: TaskDetail = sampleDetail();

  texts: Record<string, string> = { ...sampleFileTexts };

  failure: Error | null = null;

  fileCalls: string[] = [];

  taskCalls = 0;

  async fetchTasks() {
    return sampleTasks();
  }

  async fetchTask() {
    this.taskCalls += 1;

    if (this.failure) throw this.failure;

    return this.detail;
  }

  async fetchFile(_project: string, _slug: string, path: string) {
    this.fileCalls.push(path);

    if (this.failure) throw this.failure;

    return this.texts[path];
  }
}

export { sampleAgent, sampleSnapshot, sampleSummary, sampleTasks, sampleDetail, sampleFileTexts, FakeTaskClient };
