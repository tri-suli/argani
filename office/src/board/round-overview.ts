import FileTree from '@/board/file-tree';
import { fileName } from '@/board/file-view';
import ReviewParser from '@/board/review-parser';
import roundOutcome from '@/board/review-outcome';
import RoundSummary from '@/board/round-summary';
import { FILE_TONE_ICONS, TONE_LABELS, ROUND_OUTCOME_TONES, NO_TONE_ICON } from '@/constants/file-tree';
import { REVIEW_OUTCOME_CHANGES, REVIEW_OUTCOME_PASS, REVIEW_STATE_INVALID, REVIEW_STATE_PENDING } from '@/constants/review';
import {
  EMPTY_FILTER_MESSAGES, FILTER_ALL, FILTER_CHIPS, FILTER_SEVERITY, HUMAN_REVIEWER, MESSAGE_NOT_REPORTED, MESSAGE_NO_FINDING, MESSAGE_NO_FINDINGS_YET, MESSAGE_SOME_PENDING, MESSAGE_UNREADABLE, MODEL_INHERIT,
  PART_LABELS, REVIEW_FILE_NAME, ROUND_GROUP_PREFIX, ROUND_TITLE_PREFIX, SENTENCE_END, SEVERITY_ICONS, SEVERITY_RANK, STATUS_INVALID, STATUS_NOT_REPORTED, STATUS_RUNNING, STATUS_UNDECIDED,
} from '@/constants/round';
import type { FindingPartView, FindingView, FilterChip, FindingFilter, ReviewerCard, RoundOption, RoundStatus, RoundTally, RoundView, TextRenderer } from '@/types/round';
import type { ParsedFinding, ParsedReview } from '@/types/review-file';
import type { ReviewState, TaskDetail, TaskFile } from '@/types/task';

interface BuildInput {
  detail: TaskDetail;
  round: number;
  /** The text of each review file of the round by path; null for a file that could not be read. */
  texts: Record<string, string | null>;
}

/** What is known of one reviewer of a round before it becomes a card. */
interface Seat {
  name: string;
  file: TaskFile | undefined;
  parsed: ParsedReview | null;
  state: ReviewState;
}

/** The overview of one review round: reviewer cards, findings and the sentence, derived from the task detail and the review files. Pure. */
class RoundOverview {
  constructor(
    private readonly renderer: TextRenderer,
    private readonly parser: ReviewParser = new ReviewParser(),
    private readonly summary: RoundSummary = new RoundSummary(),
    private readonly fileTree: FileTree = new FileTree(),
  ) {}

  /** One option per review round of the task, in order. */
  options(detail: TaskDetail): RoundOption[] {
    return this.fileTree.roundNumbers(detail.files).sort((left, right) => left - right).map((round) => ({ round, title: this.title(round), status: this.roundStatus(detail, round) }));
  }

  /** The review files (`review-<checklist>.md`) of a round, in the order the task lists them. */
  reviewFiles(detail: TaskDetail, round: number): TaskFile[] {
    return detail.files.filter((file) => file.group === `${ROUND_GROUP_PREFIX}${round}` && REVIEW_FILE_NAME.test(fileName(file.path)));
  }

  build({ detail, round, texts }: BuildInput): RoundView {
    const running = this.isRunning(detail, round);

    const seats = this.seats(detail, round, texts);

    const cards = seats.map((seat) => this.card(seat, detail, running));

    const findings = seats.flatMap((seat) => (seat.state === REVIEW_STATE_PENDING || seat.parsed === null ? [] : seat.parsed.findings.map((finding, index) => this.findingView(seat.name, index, finding))));

    findings.sort((left, right) => SEVERITY_RANK[left.severity] - SEVERITY_RANK[right.severity]);

    const counts = { all: findings.length, important: this.countOf(findings, 'important'), nit: this.countOf(findings, 'nit') };

    return {
      round,
      title: this.title(round),
      status: this.roundStatus(detail, round),
      summary: this.summary.sentence(this.tally(seats, findings)),
      cards,
      findings,
      counts,
    };
  }

  chips(view: RoundView): FilterChip[] {
    return FILTER_CHIPS.map(({ filter, label }) => ({ filter, label, count: view.counts[filter] }));
  }

  /** The findings the filter lets through; a severity the protocol does not define shows only under All. */
  visible(view: RoundView, filter: FindingFilter): FindingView[] {
    return filter === FILTER_ALL ? view.findings : view.findings.filter((finding) => finding.severity === FILTER_SEVERITY[filter]);
  }

  /** The line shown instead of the findings when the filter leaves none; empty while there is something to show. */
  emptyMessage(view: RoundView, filter: FindingFilter): string {
    if (this.visible(view, filter).length > 0) {
      return '';
    }

    const waiting = view.cards.some((card) => card.isPending);

    if (filter === FILTER_ALL) {
      return waiting ? MESSAGE_NO_FINDINGS_YET : MESSAGE_NO_FINDING;
    }

    return EMPTY_FILTER_MESSAGES[filter] + (waiting ? MESSAGE_SOME_PENDING : SENTENCE_END);
  }

  private title(round: number): string {
    return `${ROUND_TITLE_PREFIX} ${round}`;
  }

  private isRunning(detail: TaskDetail, round: number): boolean {
    return this.fileTree.runningRound(detail.files, detail.rounds, detail.column) === round;
  }

  /** The same rule as the file list: an outcome when decided, running while the task is at work on the latest round. */
  private roundStatus(detail: TaskDetail, round: number): RoundStatus {
    const outcome = roundOutcome(detail.rounds.find((candidate) => candidate.n === round));

    if (outcome !== null) {
      const tone = ROUND_OUTCOME_TONES[outcome];

      return { label: outcome, icon: FILE_TONE_ICONS[tone], tone, spinning: false, toneLabel: TONE_LABELS[tone] };
    }

    return this.isRunning(detail, round) ? STATUS_RUNNING : STATUS_UNDECIDED;
  }

  /** The reviewers of a round: those the task lists, then review files it does not list. */
  private seats(detail: TaskDetail, round: number, texts: Record<string, string | null>): Seat[] {
    const files = new Map<string, TaskFile>();

    for (const file of this.reviewFiles(detail, round)) {
      files.set((REVIEW_FILE_NAME.exec(fileName(file.path)) as RegExpExecArray)[1], file);
    }

    const reviews = detail.rounds.find((candidate) => candidate.n === round)?.reviews ?? {};

    const names = [...Object.keys(reviews), ...[...files.keys()].filter((name) => !Object.hasOwn(reviews, name))];

    return names.map((name) => {
      const file = files.get(name);

      const text = file === undefined ? undefined : texts[file.path];

      const parsed = typeof text === 'string' ? this.parser.parse(text) : null;

      return { name, file, parsed, state: Object.hasOwn(reviews, name) ? reviews[name] : this.stateOfFile(parsed) };
    });
  }

  /** A file the task does not list has only its own words to go by; one that is cut off has not reported. */
  private stateOfFile(parsed: ParsedReview | null): ReviewState {
    if (parsed === null || !parsed.isClosed) {
      return REVIEW_STATE_PENDING;
    }

    return parsed.verdict ?? REVIEW_STATE_INVALID;
  }

  private card(seat: Seat, detail: TaskDetail, running: boolean): ReviewerCard {
    const { name, file, parsed, state } = seat;

    const isPending = state === REVIEW_STATE_PENDING;

    const readable = !isPending && parsed !== null;

    return {
      key: name,
      name,
      isHuman: name === HUMAN_REVIEWER,
      status: this.seatStatus(state, running),
      path: file?.path ?? null,
      headline: this.headline(seat),
      counts: readable ? this.countsText(parsed.findings) : '',
      model: name === HUMAN_REVIEWER ? null : this.modelOf(detail, name),
      otherNote: readable ? this.otherNote(parsed.otherLines) : '',
      isPending,
    };
  }

  private seatStatus(state: ReviewState, running: boolean): RoundStatus {
    if (state === REVIEW_OUTCOME_PASS || state === REVIEW_OUTCOME_CHANGES) {
      const tone = ROUND_OUTCOME_TONES[state];

      return { label: state, icon: FILE_TONE_ICONS[tone], tone, spinning: false, toneLabel: TONE_LABELS[tone] };
    }

    if (state === REVIEW_STATE_INVALID) {
      return STATUS_INVALID;
    }

    return running ? STATUS_RUNNING : STATUS_NOT_REPORTED;
  }

  private headline({ state, file, parsed }: Seat): string {
    if (state === REVIEW_STATE_PENDING) {
      return MESSAGE_NOT_REPORTED;
    }

    if (parsed === null) {
      return file === undefined ? '' : MESSAGE_UNREADABLE;
    }

    return parsed.headline;
  }

  private countsText(findings: ParsedFinding[]): string {
    const important = findings.filter((finding) => finding.severity === 'important').length;

    const nits = findings.filter((finding) => finding.severity === 'nit').length;

    const other = findings.length - important - nits;

    return [`${important} important`, `${nits} ${nits === 1 ? 'nit' : 'nits'}`, ...(other > 0 ? [`${other} other`] : [])].join(' · ');
  }

  private otherNote(lines: number): string {
    if (lines === 0) {
      return '';
    }

    return lines === 1 ? '1 more line that is not a finding.' : `${lines} more lines that are not findings.`;
  }

  /** The model the task detail names for a reviewer; "inherit" names none. */
  private modelOf(detail: TaskDetail, name: string): string | null {
    const reviewers = detail.models?.reviewers;

    if (typeof reviewers !== 'object' || reviewers === null || !Object.hasOwn(reviewers, name)) {
      return null;
    }

    const model = (reviewers as Record<string, unknown>)[name];

    return typeof model === 'string' && model !== MODEL_INHERIT ? model : null;
  }

  private findingView(reviewer: string, index: number, finding: ParsedFinding): FindingView {
    return {
      key: `${reviewer}:${index}`,
      severity: finding.severity,
      severityLabel: finding.severityLabel,
      icon: SEVERITY_ICONS[finding.severity],
      location: finding.location,
      reviewer,
      isHuman: reviewer === HUMAN_REVIEWER,
      parts: finding.parts.map((part): FindingPartView => ({ kind: part.kind, label: PART_LABELS[part.kind], html: this.html(part.text), isLabelled: part.kind !== 'text', isFix: part.kind === 'fix' })),
    };
  }

  /** A text of several lines (a nested list, paragraphs) is a markdown block; a single line is inline. Both are sanitized by the renderer. */
  private html(text: string): string {
    return text.includes('\n') ? this.renderer.renderMarkdown(text) : this.renderer.renderInline(text);
  }

  private countOf(findings: FindingView[], severity: FindingView['severity']): number {
    return findings.filter((finding) => finding.severity === severity).length;
  }

  private tally(seats: Seat[], findings: FindingView[]): RoundTally {
    const reviewers = seats.filter((seat) => seat.name !== HUMAN_REVIEWER);

    const stateCount = (state: ReviewState) => reviewers.filter((seat) => seat.state === state).length;

    return {
      seats: reviewers.length,
      passed: stateCount(REVIEW_OUTCOME_PASS),
      changes: stateCount(REVIEW_OUTCOME_CHANGES),
      pending: stateCount(REVIEW_STATE_PENDING),
      invalid: stateCount(REVIEW_STATE_INVALID),
      unreadable: seats.filter((seat) => seat.file !== undefined && seat.parsed === null).length,
      read: seats.filter((seat) => seat.state !== REVIEW_STATE_PENDING && seat.parsed !== null).length,
      hasHuman: seats.some((seat) => seat.name === HUMAN_REVIEWER),
      important: this.countOf(findings, 'important'),
      nits: this.countOf(findings, 'nit'),
      other: this.countOf(findings, 'other'),
    };
  }
}

export default RoundOverview;
