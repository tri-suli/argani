import { fileName, groupFiles, isMarkdownFile } from '../board/file-view';
import { formatCount, formatDuration } from '../board/format';
import { renderDocument } from '../board/markdown';
import type { TaskClient, TaskDetail } from '../board/types';
import { FOCUSABLE, PAGE_CONTENT, TONE_LABELS } from './constants';
import type { TaskDrawer } from './types';

/** The page behind the modal drawer must not be reachable by keyboard or screen reader. */
function setPageInert(inert: boolean): void {
  document.querySelectorAll(PAGE_CONTENT).forEach((element) => element.toggleAttribute('inert', inert));
}

function createTaskDrawer(taskClient: TaskClient): TaskDrawer {
  return {
    isOpen: false,
    project: '',
    slug: '',
    title: '',
    detail: null,
    selectedPath: null,
    fileText: '',
    loadedPath: null,
    loadedStamp: null,
    rendered: null,
    errorMessage: null,
    generation: 0,

    async open({ project, slug, title }) {
      Object.assign(this, { isOpen: true, project, slug, title, detail: null, selectedPath: null, fileText: '', rendered: null, loadedPath: null, loadedStamp: null, errorMessage: null });
      setPageInert(true);
      await this.load();
    },

    close() {
      if (!this.isOpen) {
        return;
      }
      this.isOpen = false;
      this.generation += 1;
      setPageInert(false);
      const key = `${this.project}/${this.slug}`;
      [...document.querySelectorAll<HTMLElement>('[data-task]')].find((card) => card.dataset.task === key)?.focus();
    },

    async select(path) {
      this.selectedPath = path;
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
        this.rendered = null;
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
          this.rendered = isMarkdownFile(file.path) ? renderDocument(text, file.tone) : null;
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

    clearFile() {
      Object.assign(this, { fileText: '', rendered: null, loadedPath: null, loadedStamp: null });
    },

    fileStamp(detail) {
      const file = detail.files.find((entry) => entry.path === this.selectedPath);
      return JSON.stringify([this.selectedPath, detail.updatedAt, file]);
    },

    trapFocus(event, container) {
      const focusable = container.querySelectorAll<HTMLElement>(FOCUSABLE);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },

    get headline() {
      const detail = this.detail;
      if (detail === null) {
        return `${this.project} · ${this.slug}`;
      }
      const parts = [detail.project, detail.slug, detail.stage, `round ${detail.round}`, detail.risk ?? '', formatDuration(detail.agentMilliseconds), `${formatCount(detail.tokens.total)} tok`];
      return parts.filter((part) => part !== '').join(' · ');
    },

    get groups() {
      return this.detail === null ? [] : groupFiles(this.detail.files);
    },

    get selectedFile() {
      return this.detail?.files.find((file) => file.path === this.selectedPath) ?? null;
    },

    fileLabel(file) {
      return fileName(file.path);
    },

    toneLabel(tone) {
      return tone === null ? '' : TONE_LABELS[tone];
    },
  };
}

export default createTaskDrawer;
