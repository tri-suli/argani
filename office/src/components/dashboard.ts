import { buildTaskHash, parseTaskRoute } from '@/board/task-route';
import { ALL_PROJECTS, APP_TITLE, CLOCK_INTERVAL_MILLISECONDS, NO_PROJECT_OPTION, TITLE_SEPARATOR } from '@/constants/dashboard';
import { STEP_LEGEND } from '@/constants/history';
import { BOARD_HASH } from '@/constants/route';
import { MILLISECONDS_PER_MINUTE, MILLISECONDS_PER_SECOND } from '@/constants/format';
import { formatDuration } from '@/board/format';
import createCommandCopier from '@/components/command-copier';
import createProjectPicker from '@/components/project-picker';
import createTaskPage from '@/components/task-page';
import type { Dashboard, DashboardDependencies } from '@/types/components';

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
function createDashboard({ poller, taskClient, boardView, historySteps, fileTree, navigation, markdownRenderer, clipboard, now }: DashboardDependencies): Dashboard {
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  return {
    snapshot: null,
    tasks: [],
    errorMessage: null,
    lastSuccessAt: null,
    clockMilliseconds: 0,
    selectedProject: ALL_PROJECTS,
    taskPage: createTaskPage(taskClient, markdownRenderer, fileTree),
    legend: STEP_LEGEND,
    picker: createProjectPicker(),
    copier: createCommandCopier(clipboard),

    init() {
      this.clockMilliseconds = now().getTime();

      // ticks every second so the "updated … ago" label keeps counting between polls
      clockTimer = setInterval(() => {
        this.clockMilliseconds = now().getTime();
      }, CLOCK_INTERVAL_MILLISECONDS);

      navigation.listen(() => this.applyRoute());

      // a link to a task opens it at once; the board data it needs arrives with the first poll
      this.applyRoute();

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

          void this.taskPage.refresh();
        },
        onError: (error) => {
          this.errorMessage = error.message;
        },
      });
    },

    destroy() {
      poller.stop();

      navigation.stop();

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

    openTask(task) {
      this.taskPage.rememberBoardPosition(window.scrollY);

      navigation.push(buildTaskHash({ project: task.project, slug: task.slug, path: null }), true);

      this.applyRoute();
    },

    leaveTask() {
      if (navigation.fromBoard()) {
        navigation.back();

        return;
      }

      navigation.replace(BOARD_HASH);

      this.applyRoute();
    },

    async selectFile(path) {
      // the address follows the click, before the file arrives: an answer that comes late must not write it
      navigation.replace(buildTaskHash({ project: this.taskPage.project, slug: this.taskPage.slug, path }));

      await this.taskPage.select(path);
    },

    applyRoute() {
      const route = parseTaskRoute(navigation.hash());

      if (route === null) {
        this.taskPage.hide();
      } else {
        void this.taskPage.show(route).then(() => this.correctAddress(route, navigation.hash()));
      }
    },

    correctAddress(route, hash) {
      // a link to a file the task does not list: the address names the file that is really shown (unless the reader has moved on)
      if (route.path !== null && navigation.hash() === hash && this.taskPage.isOpen && this.taskPage.selectedPath !== route.path) {
        navigation.replace(buildTaskHash({ project: route.project, slug: route.slug, path: this.taskPage.selectedPath }));
      }
    },

    get taskPageTask() {
      return boardView.findTask(this.snapshot, this.taskPage.project, this.taskPage.slug);
    },

    get taskSummary() {
      return this.taskPage.detail ?? this.tasks.find((summary) => summary.project === this.taskPage.project && summary.slug === this.taskPage.slug) ?? null;
    },

    get documentTitle() {
      return this.taskPage.isOpen ? `${this.taskTitle}${TITLE_SEPARATOR}${APP_TITLE}` : APP_TITLE;
    },

    get taskTitle() {
      return this.taskPageTask?.title ?? this.taskPage.slug;
    },

    get taskMissing() {
      return this.taskPage.isOpen && this.snapshot !== null && this.taskPageTask === null;
    },

    get taskHeader() {
      return this.taskPageTask === null ? null : boardView.taskHeader(this.taskPageTask, this.taskSummary);
    },

    get taskHistory() {
      return this.taskPageTask === null ? [] : historySteps.derive(this.taskPageTask, this.taskSummary, this.clockMilliseconds);
    },
  };
}

export default createDashboard;
