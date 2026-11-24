import type { Poller } from '../board/board-poller';
import { agentsWorkingOn, groupTasksByColumn, projectNames, type ColumnView } from '../board/board-view';
import type { BoardAgent, BoardSnapshot, BoardTask } from '../board/types';

export interface DashboardDependencies {
  poller: Poller;
  now: () => Date;
}

export interface Dashboard {
  snapshot: BoardSnapshot | null;
  errorMessage: string | null;
  lastSuccessAt: string | null;
  selectedProject: string;
  init(): void;
  destroy(): void;
  readonly status: string;
  readonly projects: string[];
  readonly columns: ColumnView[];
  readonly agents: BoardAgent[];
  isActive(task: BoardTask): boolean;
}

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
export function createDashboard({ poller, now }: DashboardDependencies): Dashboard {
  return {
    snapshot: null,
    errorMessage: null,
    lastSuccessAt: null,
    selectedProject: '',

    init() {
      poller.start({
        onSnapshot: (snapshot) => {
          this.snapshot = snapshot;
          if (this.selectedProject !== '' && !projectNames(snapshot).includes(this.selectedProject)) {
            this.selectedProject = '';
          }
          this.errorMessage = null;
          this.lastSuccessAt = now().toISOString();
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

    get projects() {
      return this.snapshot === null ? [] : projectNames(this.snapshot);
    },

    get columns() {
      return this.snapshot === null ? [] : groupTasksByColumn(this.snapshot, this.selectedProject || null);
    },

    get agents() {
      return this.snapshot === null ? [] : this.snapshot.agents;
    },

    isActive(task) {
      return this.snapshot !== null && agentsWorkingOn(this.snapshot.agents, task).length > 0;
    },
  };
}
