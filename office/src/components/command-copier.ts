import { COPIED_LABEL, COPY_FAILED_LABEL, COPY_FEEDBACK_MILLISECONDS, COPY_LABEL } from '@/constants/dashboard';
import type { ClipboardWriter, CommandCopier } from '@/types/components';

/** UI state only: the clipboard is injected, and a refusal is shown on the button instead of thrown. */
function createCommandCopier(clipboard: ClipboardWriter): CommandCopier {
  let resetTimer: ReturnType<typeof setTimeout> | null = null;

  let latestAttempt = 0;

  return {
    key: null,
    failed: false,

    async copy(key, command) {
      const attempt = ++latestAttempt;

      let failed = false;

      try {
        await clipboard.writeText(command);
      } catch {
        failed = true;
      }

      // a later click owns the feedback, whichever write finishes last
      if (attempt !== latestAttempt) {
        return;
      }

      this.failed = failed;

      this.key = key;

      if (resetTimer !== null) {
        clearTimeout(resetTimer);
      }

      resetTimer = setTimeout(() => {
        this.key = null;
      }, COPY_FEEDBACK_MILLISECONDS);
    },

    label(key) {
      if (this.key !== key) {
        return COPY_LABEL;
      }

      return this.failed ? COPY_FAILED_LABEL : COPIED_LABEL;
    },
  };
}

export default createCommandCopier;
