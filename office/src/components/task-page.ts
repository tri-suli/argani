import type DiffRows from '@/board/diff-rows';
import { fileName, isDiffFile, isMarkdownFile } from '@/board/file-view';
import type FileTree from '@/board/file-tree';
import type MarkdownRenderer from '@/board/markdown-renderer';
import type { TaskClient } from '@/types/client';
import type { OutlineTracker } from '@/types/document';
import type { TaskPage } from '@/types/components';
import type { TaskDetail } from '@/types/task';
import { BOARD_TITLE_SELECTOR } from '@/constants/dashboard';

function createTaskPage(taskClient: TaskClient, markdownRenderer: MarkdownRenderer, fileTree: FileTree, diffRows: DiffRows, outline: OutlineTracker): TaskPage {
  return {
    isOpen: false,
    project: '',
    slug: '',
    detail: null,
    selectedPath: null,
    fileText: '',
    loadedPath: null,
    loadedStamp: null,
    rendered: null,
    diff: null,
    outline,
    errorMessage: null,
    generation: 0,
    openRounds: null,
    knownRounds: [],
    boardScrollY: 0,
    openCount: 0,
    closeCount: 0,

    async open({ project, slug, path }) {
      Object.assign(this, { isOpen: true, project, slug, detail: null, selectedPath: path, fileText: '', rendered: null, diff: null, loadedPath: null, loadedStamp: null, errorMessage: null, openRounds: null, knownRounds: [] });

      this.openCount += 1;

      await this.load();
    },

    async show(route) {
      if (!this.isOpen || route.project !== this.project || route.slug !== this.slug) {
        await this.open(route);

        return;
      }

      if (route.path !== null && route.path !== this.selectedPath && this.detail?.files.some((file) => file.path === route.path)) {
        await this.select(route.path);
      }
    },

    hide() {
      if (!this.isOpen) {
        return;
      }

      this.isOpen = false;

      this.outline.stop();

      this.generation += 1;

      this.closeCount += 1;
    },

    rememberBoardPosition(scrollY) {
      this.boardScrollY = scrollY;
    },

    restoreBoard() {
      const key = `${this.project}/${this.slug}`;

      // Alpine shows the board after this runs in the same tick: scrolling and focusing need it laid out, so wait for the next frame
      requestAnimationFrame(() => {
        window.scrollTo(0, this.boardScrollY);

        const opener = [...document.querySelectorAll<HTMLElement>('[data-task]')].find((element) => element.dataset.task === key);

        // the opener may be gone after a poll: the heading of the board is the next best place for the focus
        (opener ?? document.querySelector<HTMLElement>(BOARD_TITLE_SELECTOR))?.focus();
      });
    },

    focusTitle(title) {
      window.scrollTo(0, 0);

      title.focus();
    },

    async select(path) {
      this.selectedPath = path;

      this.openRounds = fileTree.withRoundOf(this.openRounds as number[], path, (this.detail as TaskDetail).files);

      this.clearFile();

      await this.loadFile(++this.generation);
    },

    async refresh() {
      if (this.isOpen) {
        await this.load();
      }
    },

    async load() {
      const generation = ++this.generation;

      try {
        const detail = await taskClient.fetchTask(this.project, this.slug);

        if (generation !== this.generation) {
          return;
        }

        this.detail = detail;

        if (!detail.files.some((file) => file.path === this.selectedPath)) {
          this.selectedPath = detail.files[0]?.path ?? null;

          this.clearFile();
        }

        this.chooseOpenRounds(detail);

        // shortcut: updatedAt has one-second resolution, so a rewrite within the second of the last fetch is
        // missed until the next change; upgrade to a size/mtime in the file listing if that ever shows.
        if (this.selectedFile === null || this.fileStamp(detail) !== this.loadedStamp) {
          await this.loadFile(generation);
        }
      } catch (error) {
        // A failed refresh keeps what is on screen; the board banner already reports an unreachable backend.
        if (generation === this.generation && this.detail === null) {
          this.errorMessage = (error as Error).message;
        }
      }
    },

    async loadFile(generation) {
      const file = this.selectedFile;

      if (file === null) {
        this.fileText = '';

        Object.assign(this, { rendered: null, diff: null });

        return;
      }

      try {
        const text = await taskClient.fetchFile(this.project, this.slug, file.path);

        if (generation !== this.generation) {
          return;
        }

        // an identical file keeps its objects, so x-html does not rebuild the DOM (focus and selection survive)
        if (this.loadedPath !== file.path || text !== this.fileText) {
          this.fileText = text;

          this.rendered = isMarkdownFile(file.path) ? markdownRenderer.renderDocument(text, file.tone) : null;

          this.diff = isDiffFile(file.path) ? diffRows.parse(text) : null;
        }

        this.loadedPath = file.path;

        this.loadedStamp = this.fileStamp(this.detail as TaskDetail);

        this.errorMessage = null;
      } catch (error) {
        if (generation === this.generation) {
          this.errorMessage = (error as Error).message;
        }
      }
    },

    chooseOpenRounds(detail) {
      const numbers = fileTree.roundNumbers(detail.files);

      if (this.openRounds === null) {
        this.openRounds = fileTree.initialOpenRounds(detail.files, detail.rounds, detail.column, this.selectedPath);
      } else {
        // a round that is new and already running opens once; the rounds the reader has seen keep the reader's choice
        const running = fileTree.runningRound(detail.files, detail.rounds, detail.column);

        if (running !== null && !this.knownRounds.includes(running) && !this.openRounds.includes(running)) {
          this.openRounds = fileTree.toggled(this.openRounds, running);
        }
      }

      this.knownRounds = numbers;
    },

    clearFile() {
      Object.assign(this, { fileText: '', rendered: null, diff: null, loadedPath: null, loadedStamp: null });
    },

    fileStamp(detail) {
      const file = detail.files.find((entry) => entry.path === this.selectedPath);

      return JSON.stringify([this.selectedPath, detail.updatedAt, file]);
    },

    toggleRound(round) {
      this.openRounds = fileTree.toggled(this.openRounds as number[], round);
    },

    get sections() {
      return this.detail === null ? [] : fileTree.sections(this.detail.files, this.detail.rounds, this.detail.column, this.openRounds as number[]);
    },

    get selectedFile() {
      return this.detail?.files.find((file) => file.path === this.selectedPath) ?? null;
    },

    get selectedFileName() {
      return this.selectedPath === null ? '' : fileName(this.selectedPath);
    },

    get sectionIds() {
      return this.rendered === null ? [] : this.rendered.outline.map((entry) => entry.id);
    },

    trackSections() {
      const ids = this.sectionIds;

      // the document is drawn in this tick: observe its headings on the next frame
      requestAnimationFrame(() => this.outline.track(ids));
    },
  };
}

export default createTaskPage;
