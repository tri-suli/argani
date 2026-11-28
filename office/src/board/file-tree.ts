import roundOutcome from '@/board/review-outcome';
import { fileName, groupFiles } from '@/board/file-view';
import { DIFF_FILE_NAME, DIFF_ICON, FILE_TONE_ICONS, NO_TONE_ICON, REVIEW_SECTION_NAME, ROUND_GROUP_PATTERN, ROUND_LABEL_PREFIX, ROUND_OUTCOME_TONES, RUNNING_ICON, RUNNING_LABEL, RUNNING_TAG, TONE_LABELS, TONE_NONE, TONE_NOW, WORD_SEPARATOR } from '@/constants/file-tree';
import { WORKING_COLUMNS } from '@/constants/pipeline';
import type { FileRow, FileSection } from '@/types/file-tree';
import type { TaskFile, TaskRound } from '@/types/task';
import type { FileGroup } from '@/types/view';

/** The file list of a task page: the files the server lists, with each review round as a row that opens and closes. */
class FileTree {
  /** The sections of the list; the files of a round are listed only while the round is in `openRounds`. */
  sections(files: TaskFile[], rounds: TaskRound[], column: string, openRounds: number[]): FileSection[] {
    const groups = groupFiles(files);

    const numbers = this.roundNumbers(groups);

    const latest = numbers.length === 0 ? null : Math.max(...numbers);

    const sections: FileSection[] = [];

    let review: FileSection | null = null;

    for (const group of groups) {
      const round = this.roundNumber(group.name);

      if (round === null) {
        sections.push({ name: group.name, rows: group.files.map((file) => this.fileRow(file, false)) });

        continue;
      }

      if (review === null) {
        review = { name: REVIEW_SECTION_NAME, rows: [] };

        sections.push(review);
      }

      const expanded = openRounds.includes(round);

      review.rows.push(this.roundRow(round, rounds, column, latest, expanded));

      if (expanded) {
        review.rows.push(...group.files.map((file) => this.fileRow(file, true)));
      }
    }

    return sections;
  }

  /** The round that is running, otherwise the latest, plus the round of the selected file. */
  initialOpenRounds(files: TaskFile[], rounds: TaskRound[], column: string, selectedPath: string | null): number[] {
    const numbers = this.roundNumbers(groupFiles(files));

    const latest = numbers.length === 0 ? null : Math.max(...numbers);

    const open = numbers.find((round) => this.isRunning(round, rounds, column, latest)) ?? latest;

    return this.withRoundOf(open === null ? [] : [open], selectedPath, files);
  }

  toggled(openRounds: number[], round: number): number[] {
    return openRounds.includes(round) ? openRounds.filter((open) => open !== round) : [...openRounds, round].sort((left, right) => left - right);
  }

  /** The list with the round of the file in it, so a file picked by a link is not hidden in a closed round. */
  withRoundOf(openRounds: number[], path: string | null, files: TaskFile[]): number[] {
    const group = files.find((file) => file.path === path)?.group;

    const round = group === undefined ? null : this.roundNumber(group);

    return round === null || openRounds.includes(round) ? openRounds : this.toggled(openRounds, round);
  }

  private roundNumber(groupName: string): number | null {
    const match = ROUND_GROUP_PATTERN.exec(groupName);

    return match === null ? null : Number(match[1]);
  }

  private roundNumbers(groups: FileGroup[]): number[] {
    return groups.map((group) => this.roundNumber(group.name)).filter((round) => round !== null);
  }

  /** Running: the latest round, undecided, while the task is with the agents. */
  private isRunning(round: number, rounds: TaskRound[], column: string, latest: number | null): boolean {
    return round === latest && WORKING_COLUMNS.has(column) && roundOutcome(rounds.find((candidate) => candidate.n === round)) === null;
  }

  private roundRow(round: number, rounds: TaskRound[], column: string, latest: number | null, expanded: boolean): FileRow {
    const outcome = roundOutcome(rounds.find((candidate) => candidate.n === round));

    const running = this.isRunning(round, rounds, column, latest);

    const label = `${ROUND_LABEL_PREFIX} ${round}`;

    const shared = { key: `round:${round}`, kind: 'round' as const, label, tagTitle: '', nested: false, path: null, round, expanded };

    if (outcome !== null) {
      const tone = ROUND_OUTCOME_TONES[outcome];

      return { ...shared, icon: FILE_TONE_ICONS[tone], tone, tag: outcome, spinning: false, toneLabel: TONE_LABELS[tone] };
    }

    return running
      ? { ...shared, icon: RUNNING_ICON, tone: TONE_NOW, tag: RUNNING_TAG, spinning: true, toneLabel: RUNNING_LABEL }
      : { ...shared, icon: NO_TONE_ICON, tone: TONE_NONE, tag: '', spinning: false, toneLabel: '' };
  }

  private fileRow(file: TaskFile, nested: boolean): FileRow {
    const name = fileName(file.path);

    const tone = file.tone ?? TONE_NONE;

    return {
      key: `file:${file.path}`,
      kind: 'file',
      label: name,
      icon: file.tone === null ? (name === DIFF_FILE_NAME ? DIFF_ICON : NO_TONE_ICON) : FILE_TONE_ICONS[file.tone],
      tone,
      tag: file.tone === null ? '' : file.firstLine.split(WORD_SEPARATOR)[0],
      tagTitle: file.firstLine,
      nested,
      path: file.path,
      round: null,
      expanded: false,
      spinning: false,
      toneLabel: file.tone === null ? '' : TONE_LABELS[file.tone],
    };
  }
}

export default FileTree;
