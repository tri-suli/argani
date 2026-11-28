import { ALL_PROJECTS, CLOCK_INTERVAL_MILLISECONDS, NO_COUNT, NO_PROJECT_OPTION } from '@/constants/dashboard';
import { MILLISECONDS_PER_MINUTE, MILLISECONDS_PER_SECOND } from '@/constants/format';
import { formatDuration } from '@/board/format';
import createCommandCopier from '@/components/command-copier';
import createProjectPicker from '@/components/project-picker';
import createTaskDrawer from '@/components/task-drawer';
import type { Dashboard, DashboardDependencies } from '@/types/components';

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
function createDashboard({ poller, taskClient, boardView, markdownRenderer, clipboard, now }: DashboardDependencies): Dashboard {
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  return {
    snapshot: null,
    tasks: [],
    errorMessage: null,
    lastSuccessAt: null,
    clockMilliseconds: 0,
    selectedProject: ALL_PROJECTS,
    drawer: createTaskDrawer(taskClient, markdownRenderer),
    picker: createProjectPicker(),
    copier: createCommandCopier(clipboard),

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

    get projectOptions() {
      return this.snapshot === null ? [] : boardView.projectOptions(this.snapshot);
    },

    get matchingProjectOptions() {
      return boardView.searchProjectOptions(this.projectOptions, this.picker.query);
    },

    get selectedOption() {
      return this.projectOptions.find((option) => option.value === this.selectedProject) ?? NO_PROJECT_OPTION;
    },

    get columns() {
      return this.snapshot === null ? [] : boardView.groupTasksByColumn(this.snapshot, this.tasks, this.selectedProject || null, this.clockMilliseconds);
    },

    get tiles() {
      return this.snapshot === null ? [] : boardView.totalTiles(this.snapshot, this.tasks, this.selectedProject || null, this.clockMilliseconds);
    },

    get needsHumanRows() {
      return this.snapshot === null ? [] : boardView.needsHumanRows(this.snapshot, this.selectedProject || null, this.clockMilliseconds);
    },

    get doneRows() {
      return this.snapshot === null ? [] : boardView.doneRows(this.snapshot, this.tasks, this.selectedProject || null);
    },

    chooseProject(value, button) {
      this.selectedProject = value;

      this.closePicker(button);
    },

    closePicker(button) {
      this.picker.close();

      button.focus();
    },

    get drawerTask() {
      return boardView.findTask(this.snapshot, this.drawer.project, this.drawer.slug);
    },

    get drawerWaiting() {
      return formatDuration(this.drawerTask?.metrics.needsHumanMilliseconds ?? 0);
    },

    get drawerHasHistory() {
      return this.drawerHistory.length > NO_COUNT;
    },

    get drawerHistory() {
      return this.drawerTask === null ? [] : boardView.historyRows(this.drawerTask);
    },
  };
}

export default createDashboard;
