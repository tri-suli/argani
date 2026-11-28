import type DiffRows from '@/board/diff-rows';
import { fileName, isDiffFile, isMarkdownFile } from '@/board/file-view';
import type FileTree from '@/board/file-tree';
import type MarkdownRenderer from '@/board/markdown-renderer';
import type RoundOverview from '@/board/round-overview';
import type { TaskClient } from '@/types/client';
import type { OutlineTracker } from '@/types/document';
import type { TaskPage } from '@/types/components';
import type { TaskDetail, TaskFile } from '@/types/task';
import { BOARD_TITLE_SELECTOR } from '@/constants/dashboard';
import { FILTER_ALL, FRAGMENT_LINK_SELECTOR } from '@/constants/round';

function createTaskPage(taskClient: TaskClient, markdownRenderer: MarkdownRenderer, fileTree: FileTree, diffRows: DiffRows, roundOverview: RoundOverview, outline: OutlineTracker): TaskPage {
  // The review files read for the overview, by task and path: not state of the page, so a poll that finds them unchanged draws nothing.
  const reviewTexts = new Map<string, { stamp: string; text: string }>();

  /**
   * The text of a review file: the one read before while its listing, the task's last change and the verdicts of the round are the same,
   * otherwise a fresh read. updatedAt has a one-second resolution, so a file read while it was being written (no closing line yet) is never kept.
   */
  const readReview = async (project: string, slug: string, file: TaskFile, version: unknown[], failures: string[]): Promise<string | null> => {
    const key = `${project}/${slug}/${file.path}`;

    const stamp = JSON.stringify([...version, file]);

    const cached = reviewTexts.get(key);

    if (cached?.stamp === stamp) {
      return cached.text;
    }

    try {
      const text = await taskClient.fetchFile(project, slug, file.path);

      if (roundOverview.isComplete(text)) {
        reviewTexts.set(key, { stamp, text });
      } else {
        reviewTexts.delete(key);
      }

      return text;
    } catch (error) {
      failures.push((error as Error).message);

      // the last good text stays on screen until a read succeeds
      return cached?.text ?? null;
    }
  };

  return {
    isOpen: false,
    project: '',
    slug: '',
    detail: null,
    selectedPath: null,
    selectedRound: null,
    round: null,
    roundSignature: '',
    findingFilter: FILTER_ALL,
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

    async open({ project, slug, path, round }) {
      Object.assign(this, { isOpen: true, project, slug, detail: null, selectedPath: path, selectedRound: round ?? null, round: null, roundSignature: '', findingFilter: FILTER_ALL, fileText: '', rendered: null, diff: null, loadedPath: null, loadedStamp: null, errorMessage: null, openRounds: null, knownRounds: [] });

      reviewTexts.clear();

      this.openCount += 1;

      await this.load();
    },

    async show(route) {
      if (!this.isOpen || route.project !== this.project || route.slug !== this.slug) {
        await this.open(route);

        return;
      }

      const detail = this.detail;

      // the task is still loading: what the address names is the selection, and load() checks it against the task once it has arrived
      if (detail === null) {
        if (route.round !== undefined) {
          Object.assign(this, { selectedPath: null, selectedRound: route.round, findingFilter: FILTER_ALL });
        } else if (route.path !== null) {
          Object.assign(this, { selectedPath: route.path, selectedRound: null });
        }

        return;
      }

      if (route.round !== undefined) {
        if (route.round !== this.selectedRound && fileTree.roundNumbers(detail.files).includes(route.round)) {
          await this.selectRound(route.round);
        }

        return;
      }

      if (route.path !== null && route.path !== this.selectedPath && detail.files.some((file) => file.path === route.path)) {
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

      Object.assign(this, { selectedRound: null, round: null, roundSignature: '' });

      this.openRounds = fileTree.withRoundOf(this.openRounds as number[], path, (this.detail as TaskDetail).files);

      this.clearFile();

      await this.loadFile(++this.generation);
    },

    async selectRound(round) {
      if (round === this.selectedRound) {
        return;
      }

      Object.assign(this, { selectedPath: null, selectedRound: round, round: null, roundSignature: '', findingFilter: FILTER_ALL });

      this.openRounds = (this.openRounds as number[]).includes(round) ? this.openRounds : fileTree.toggled(this.openRounds as number[], round);

      this.clearFile();

      await this.loadRound(++this.generation);
    },

    setFindingFilter(filter) {
      this.findingFilter = filter;
    },

    ignoreFragmentLinks(event) {
      if ((event.target as Element).closest(FRAGMENT_LINK_SELECTOR) !== null) {
        event.preventDefault();
      }
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

        // a round that is no longer there leaves the page on the first file, like a file that is gone
        if (this.selectedRound !== null && !fileTree.roundNumbers(detail.files).includes(this.selectedRound)) {
          Object.assign(this, { selectedRound: null, round: null, roundSignature: '' });
        }

        if (this.selectedRound === null && !detail.files.some((file) => file.path === this.selectedPath)) {
          this.selectedPath = detail.files[0]?.path ?? null;

          this.clearFile();
        }

        this.chooseOpenRounds(detail);

        if (this.selectedRound !== null) {
          await this.loadRound(generation);

          return;
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

    async loadRound(generation) {
      const detail = this.detail as TaskDetail;

      const round = this.selectedRound as number;

      const failures: string[] = [];

      const files = roundOverview.reviewFiles(detail, round);

      const version = [detail.updatedAt, detail.rounds.find((candidate) => candidate.n === round)?.reviews];

      const read = await Promise.all(files.map((file) => readReview(this.project, this.slug, file, version, failures)));

      if (generation !== this.generation) {
        return;
      }

      const texts = Object.fromEntries(files.map((file, index) => [file.path, read[index]]));

      // what the view is made of: an identical poll keeps the cards (and the scroll and focus inside them) as they are
      const signature = JSON.stringify([round, detail.column, detail.models, detail.rounds.find((candidate) => candidate.n === round), files, texts]);

      if (signature !== this.roundSignature) {
        this.round = roundOverview.build({ detail, round, texts });

        this.roundSignature = signature;
      }

      this.errorMessage = failures[0] ?? null;
    },

    chooseOpenRounds(detail) {
      const numbers = fileTree.roundNumbers(detail.files);

      if (this.openRounds === null) {
        const initial = fileTree.initialOpenRounds(detail.files, detail.rounds, detail.column, this.selectedPath);

        this.openRounds = this.selectedRound === null || initial.includes(this.selectedRound) ? initial : fileTree.toggled(initial, this.selectedRound);
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

    get roundOptions() {
      return this.detail === null ? [] : roundOverview.options(this.detail);
    },

    get selectedRoundOption() {
      return this.roundOptions.find((option) => option.round === this.selectedRound) ?? null;
    },

    get roundChips() {
      return this.round === null ? [] : roundOverview.chips(this.round);
    },

    get visibleFindings() {
      return this.round === null ? [] : roundOverview.visible(this.round, this.findingFilter);
    },

    get emptyFindingsMessage() {
      return this.round === null ? '' : roundOverview.emptyMessage(this.round, this.findingFilter);
    },

    get visibleNotes() {
      return this.round === null ? [] : roundOverview.visibleNotes(this.round, this.findingFilter);
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

    copyKey(block) {
      return `${this.selectedPath}#${block.key}#${block.text}`;
    },

    trackSections() {
      const ids = this.sectionIds;

      // the document is drawn in this tick: observe its headings on the next frame
      requestAnimationFrame(() => this.outline.track(ids));
    },
  };
}

export default createTaskPage;
