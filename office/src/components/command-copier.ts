import { COPIED_LABEL, COPY_FAILED_LABEL, COPY_FEEDBACK_MILLISECONDS, COPY_LABEL } from '@/constants/dashboard';
import type { ClipboardWriter, CommandCopier } from '@/types/components';

/** UI state only: the clipboard is injected, and a refusal is shown on the button instead of thrown. */
function createCommandCopier(clipboard: ClipboardWriter): CommandCopier {
  let resetTimer: ReturnType<typeof setTimeout> | null = null;

  return {
    key: null,
    failed: false,

    async copy(key, command) {
      try {
        await clipboard.writeText(command);

        this.failed = false;
      } catch {
        this.failed = true;
      }

      this.key = key;

      if (resetTimer !== null) {
        clearTimeout(resetTimer);
      }

      resetTimer = setTimeout(() => {
        this.key = null;
      }, COPY_FEEDBACK_MILLISECONDS);
    },

    isCopied(key) {
      return this.key === key && !this.failed;
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
