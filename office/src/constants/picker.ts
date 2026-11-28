/** What the arrow keys move between inside the project picker: the search field, then the options. */
const PICKER_ITEMS = 'input, [role="option"]';

const PICKER_KEY_STEPS: Record<string, number> = { ArrowDown: 1, ArrowUp: -1 };

export {
  PICKER_ITEMS,
  PICKER_KEY_STEPS,
};
