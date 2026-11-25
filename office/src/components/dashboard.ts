import { groupTasksByColumn, projectNames, totalTokens } from '../board/board-view';
import { formatCount, formatDuration } from '../board/format';
import { CLOCK_INTERVAL_MILLISECONDS } from './constants';
import { createTaskDrawer } from './task-drawer';
import type { Dashboard, DashboardDependencies } from './types';

export function createDashboard({ poller, taskClient, now }: DashboardDependencies): Dashboard {
  let clockTimer: ReturnType<typeof setInterval> | null = null;
  return {
    snapshot: null,
    tasks: [],
    errorMessage: null,
    lastSuccessAt: null,
    clockMilliseconds: 0,
    selectedProject: '',
    drawer: createTaskDrawer(taskClient),

    init() {
      this.clockMilliseconds = now().getTime();
      // ticks every second so the "updated … ago" label keeps counting between polls
      clockTimer = setInterval(() => {
        this.clockMilliseconds = now().getTime();
      }, CLOCK_INTERVAL_MILLISECONDS);
      poller.start({
        onSnapshot: (snapshot, tasks) => {
          this.snapshot = snapshot;
          this.tasks = tasks;
          if (this.selectedProject !== '' && !projectNames(snapshot).includes(this.selectedProject)) {
            this.selectedProject = '';
          }
          this.errorMessage = null;
          this.clockMilliseconds = now().getTime();
          this.lastSuccessAt = new Date(this.clockMilliseconds).toISOString();
          void this.drawer.refresh();
        },
        onError: (error) => {
          this.errorMessage = error.message;
        },
      });
    },

    destroy() {
      poller.stop();
      if (clockTimer !== null) {
        clearInterval(clockTimer);
        clockTimer = null;
      }
    },

    get status() {
      if (this.errorMessage !== null) {
        return 'Disconnected';
      }
      return this.snapshot === null ? 'Connecting' : 'Connected';
    },

    get updatedLabel() {
      if (this.lastSuccessAt === null) {
        return '';
      }
      const age = Math.max(0, this.clockMilliseconds - Date.parse(this.lastSuccessAt));
      return age < 60_000 ? `updated ${Math.floor(age / 1000)}s ago` : `updated ${formatDuration(age)} ago`;
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
