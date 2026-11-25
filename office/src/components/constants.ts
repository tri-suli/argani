import type { FileTone } from '../board/types';

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
const CLOCK_INTERVAL_MILLISECONDS = 1000;

const TONE_LABELS: Record<FileTone, string> = { good: 'passed', warn: 'changes requested', stop: 'escalated' };

const FOCUSABLE = 'button, a[href], [tabindex]:not([tabindex="-1"])';
const PAGE_CONTENT = '.page > :not(.drawer-root)';

export { CLOCK_INTERVAL_MILLISECONDS, TONE_LABELS, FOCUSABLE, PAGE_CONTENT };
