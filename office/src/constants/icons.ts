// Every Material Symbols ligature the page can render, the single source of truth for the committed font subset
// (src/assets/fonts, see office/README.md). The markup spells its names out; the TypeScript refers to them by key.
const ICON = {
  arrowBack: 'arrow_back',
  arrowForward: 'arrow_forward',
  block: 'block',
  cancel: 'cancel',
  check: 'check',
  checkBox: 'check_box',
  checkBoxOutlineBlank: 'check_box_outline_blank',
  checkCircle: 'check_circle',
  chevronRight: 'chevron_right',
  dashboard: 'dashboard',
  description: 'description',
  difference: 'difference',
  editNote: 'edit_note',
  error: 'error',
  expandMore: 'expand_more',
  folderOpen: 'folder_open',
  help: 'help',
  hourglassTop: 'hourglass_top',
  info: 'info',
  merge: 'merge',
  moreHoriz: 'more_horiz',
  openInNew: 'open_in_new',
  person: 'person',
  personRaisedHand: 'person_raised_hand',
  priorityHigh: 'priority_high',
  progressActivity: 'progress_activity',
  search: 'search',
  shield: 'shield',
  terminal: 'terminal',
  unfoldMore: 'unfold_more',
  viewColumn: 'view_column',
  warning: 'warning',
} as const;

const ICON_NAMES: string[] = Object.values(ICON).sort();

export { ICON, ICON_NAMES };
