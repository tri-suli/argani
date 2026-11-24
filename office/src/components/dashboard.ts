import type { Poller } from '../board/board-poller';
import { groupTasksByColumn, projectNames, totalTokens, type ColumnView } from '../board/board-view';
import { formatCount } from '../board/format';
import type { TaskClient } from '../board/task-client';
import type { BoardSnapshot, TaskSummary } from '../board/types';
import { createTaskDrawer, type TaskDrawer } from './task-drawer';

export interface DashboardDependencies {
  poller: Poller;
  taskClient: TaskClient;
  now: () => Date;
}

export interface Dashboard {
  snapshot: BoardSnapshot | null;
  tasks: TaskSummary[];
  errorMessage: string | null;
  lastSuccessAt: string | null;
  selectedProject: string;
  drawer: TaskDrawer;
  init(): void;
  destroy(): void;
  readonly status: string;
  readonly updatedLabel: string;
  readonly projects: string[];
  readonly columns: ColumnView[];
  readonly agentsRunning: number;
  readonly tokensLabel: string;
}

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
export function createDashboard({ poller, taskClient, now }: DashboardDependencies): Dashboard {
  return {
    snapshot: null,
    tasks: [],
    errorMessage: null,
    lastSuccessAt: null,
    selectedProject: '',
    drawer: createTaskDrawer(taskClient),

    init() {
      poller.start({
        onSnapshot: (snapshot, tasks) => {
          this.snapshot = snapshot;
          this.tasks = tasks;
          if (this.selectedProject !== '' && !projectNames(snapshot).includes(this.selectedProject)) {
            this.selectedProject = '';
          }
          this.errorMessage = null;
          this.lastSuccessAt = now().toISOString();
          void this.drawer.refresh();
        },
        onError: (error) => {
          this.errorMessage = error.message;
        },
      });
    },

    destroy() {
      poller.stop();
    },

    get status() {
      if (this.errorMessage !== null) {
        return 'Disconnected';
      }
      return this.snapshot === null ? 'Connecting' : 'Connected';
    },

    get updatedLabel() {
      return this.lastSuccessAt === null ? '' : new Date(this.lastSuccessAt).toLocaleTimeString('en-GB');
    },

    get projects() {
      return this.snapshot === null ? [] : projectNames(this.snapshot);
    },

    get columns() {
      return this.snapshot === null ? [] : groupTasksByColumn(this.snapshot, this.tasks, this.selectedProject || null);
    },

    get agentsRunning() {
      return this.snapshot === null ? 0 : this.snapshot.agents.length;
    },

    get tokensLabel() {
      return formatCount(totalTokens(this.tasks));
    },
  };
}
