import type { FileTone } from '../board/types';

/** UI state only: all polling and grouping logic lives in injected or pure modules. */
export const CLOCK_INTERVAL_MILLISECONDS = 1000;

export const TONE_LABELS: Record<FileTone, string> = { good: 'passed', warn: 'changes requested', stop: 'escalated' };

export const FOCUSABLE = 'button, a[href], [tabindex]:not([tabindex="-1"])';
export const PAGE_CONTENT = '.page > :not(.drawer-root)';
