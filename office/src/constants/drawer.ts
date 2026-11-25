import type { FileTone } from '@/types/task';

const TONE_LABELS: Record<FileTone, string> = { good: 'passed', warn: 'changes requested', stop: 'escalated' };

const FOCUSABLE = 'button, a[href], [tabindex]:not([tabindex="-1"])';

const PAGE_CONTENT = '.page > :not(.drawer-root)';

export {
  TONE_LABELS,
  FOCUSABLE,
  PAGE_CONTENT,
};
