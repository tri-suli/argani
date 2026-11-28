import { PICKER_ITEMS, PICKER_KEY_STEPS } from '@/constants/picker';
import type { ProjectPicker } from '@/types/components';

/** UI state only: which options exist and which is chosen is decided by BoardView and the dashboard. */
function createProjectPicker(): ProjectPicker {
  return {
    isOpen: false,
    query: '',

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.isOpen = true;
      }
    },

    close() {
      this.isOpen = false;

      this.query = '';
    },

    /** Arrow keys move the focus between the search field and the options, stopping at both ends. */
    navigate(event, container) {
      const step = PICKER_KEY_STEPS[event.key];

      if (step === undefined) {
        return;
      }

      event.preventDefault();

      const items = [...container.querySelectorAll<HTMLElement>(PICKER_ITEMS)];

      const target = Math.min(Math.max(items.indexOf(document.activeElement as HTMLElement) + step, 0), items.length - 1);

      items[target]?.focus();
    },
  };
}

export default createProjectPicker;
