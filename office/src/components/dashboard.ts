import { ALL_PROJECTS } from '@/constants/dashboard';
import { MILLISECONDS_PER_MINUTE, MILLISECONDS_PER_SECOND } from '@/constants/format';
import { formatCount, formatDuration } from '@/board/format';
import { CLOCK_INTERVAL_MILLISECONDS } from '@/constants/dashboard';
import createTaskDrawer from '@/components/task-drawer';
import type { Dashboard, DashboardDependencies } from '@/types/components';

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
function createDashboard({ poller, taskClient, boardView, markdownRenderer, now }: DashboardDependencies): Dashboard {
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  return {
    snapshot: null,
    tasks: [],
    errorMessage: null,
    lastSuccessAt: null,
    clockMilliseconds: 0,
    selectedProject: ALL_PROJECTS,
    drawer: createTaskDrawer(taskClient, markdownRenderer),

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

          if (this.selectedProject !== ALL_PROJECTS && !boardView.projectNames(snapshot).includes(this.selectedProject)) {
            this.selectedProject = ALL_PROJECTS;
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

      return age < MILLISECONDS_PER_MINUTE ? `updated ${Math.floor(age / MILLISECONDS_PER_SECOND)}s ago` : `updated ${formatDuration(age)} ago`;
    },

    get projects() {
      return this.snapshot === null ? [] : boardView.projectNames(this.snapshot);
    },

    get columns() {
      return this.snapshot === null ? [] : boardView.groupTasksByColumn(this.snapshot, this.tasks, this.selectedProject || null);
    },

    get agentsRunning() {
      return this.snapshot === null ? 0 : this.snapshot.agents.length;
    },

    get tokensLabel() {
      return formatCount(boardView.totalTokens(this.tasks));
    },
  };
}

export default createDashboard;
