import BoardView from '@/board/board-view';
import FileTree from '@/board/file-tree';
import HistorySteps from '@/board/history-steps';
import type { BoardAgent, BoardSnapshot, BoardTask } from '@/types/board';
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

const noMetrics = { manualAcceptanceCriteria: 0, needsHumanCount: 0, needsHumanMilliseconds: 0 };

function sampleTask(overrides: Partial<BoardTask> & Pick<BoardTask, 'project' | 'slug'>): BoardTask {
  return { title: overrides.slug, stage: 'needs-build', column: 'Build', merged: null, next: '-', reason: null, question: null, history: [], durations: [], metrics: noMetrics, ...overrides };
}

function sampleSnapshot(overrides: Partial<BoardSnapshot> = {}): BoardSnapshot {
  return {
    home: '/home/user/.argani',
    generatedAt: '2026-11-24T10:00:05Z',
    columns: ['Intake', 'Spec', 'Build', 'Review', 'Approve', 'Needs human', 'Done'],
    projects: [
      {
        name: 'demo',
        tasks: [
          sampleTask({ project: 'demo', slug: 'add-login', title: 'Add login', stage: 'needs-intent-approval', column: 'Intake', next: 'approve intent' }),
          sampleTask({ project: 'demo', slug: 'fix-export', title: 'Fix export', next: 'build' }),
          sampleTask({ project: 'demo', slug: 'older', title: 'Older work', stage: 'needs-review', column: 'Review' }),
          sampleTask({
            project: 'demo',
            slug: 'stuck',
            title: 'Stuck task',
            stage: 'needs-human',
            column: 'Needs human',
            next: 'Stop: a human must answer',
            reason: 'manual-verification',
            question: 'decide the schema',
            history: [
              { ts: '2026-11-24T08:00:00Z', stage: 'needs-build', column: 'Build', reason: null },
              { ts: '2026-11-24T09:00:00Z', stage: 'needs-human', column: 'Needs human', reason: 'manual-verification' },
              { ts: '2026-11-24T09:10:00Z', stage: 'needs-build', column: 'Build', reason: null },
              { ts: '2026-11-24T09:20:00Z', stage: 'needs-human', column: 'Needs human', reason: 'manual-verification' },
            ],
            durations: [
              { column: 'Build', milliseconds: 3_600_000 },
              { column: 'Needs human', milliseconds: 600_000 },
              { column: 'Build', milliseconds: 600_000 },
              { column: 'Needs human', milliseconds: 900_000 },
            ],
            metrics: { manualAcceptanceCriteria: 2, needsHumanCount: 2, needsHumanMilliseconds: 1_500_000 },
          }),
        ],
      },
      {
        name: 'other',
        tasks: [
          sampleTask({ project: 'other', slug: 'ship', title: 'Ship it', stage: 'done', column: 'Done', merged: true, metrics: { ...noMetrics, manualAcceptanceCriteria: 1, needsHumanMilliseconds: 600_000 } }),
          sampleTask({ project: 'other', slug: 'dropped', title: 'Dropped idea', stage: 'cancelled', column: 'Done', merged: false }),
          // a column that is not a pipeline column (an unreadable task of a broken project) is shown as Needs human, with its message
          sampleTask({ project: 'other', slug: 'blocked', title: 'Blocked task', stage: 'error', column: 'Unreadable', question: 'tasks.json is unreadable' }),
        ],
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
    sampleSummary({ project: 'other', slug: 'dropped', stage: 'cancelled', updatedAt: '2026-11-21T08:00:00Z' }),
  ];
}

function sampleDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    ...sampleSummary({ project: 'demo', slug: 'fix-export', risk: 'medium', round: 1, mrUrl: 'https://example.test/mr/7', agentMilliseconds: 125000, tokens: { ...noTokens, total: 6000 } }),
    stage: 'build',
    next: 'review',
    column: 'Build',
    rounds: [{ n: 1, reviews: { code: 'PASS' } }],
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

/** The pure view modules a dashboard is built with. */
function sampleViews() {
  return { boardView: new BoardView(), historySteps: new HistorySteps(), fileTree: new FileTree() };
}

export { sampleViews, sampleAgent, sampleTask, sampleSnapshot, sampleSummary, sampleTasks, sampleDetail, sampleFileTexts, FakeTaskClient };
