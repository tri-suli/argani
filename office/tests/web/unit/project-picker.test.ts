// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';
import createProjectPicker from '@/components/project-picker';

const container = () => document.querySelector('#menu') as HTMLElement;

const items = () => [...container().querySelectorAll<HTMLElement>('input, [role=option]')];

const press = (picker: ReturnType<typeof createProjectPicker>, key: string) => {
  const event = new KeyboardEvent('keydown', { key, cancelable: true });

  picker.navigate(event, container());

  return event;
};

beforeEach(() => {
  document.body.innerHTML = '<div id="menu"><input><ul><li role="option" tabindex="-1"></li><li role="option" tabindex="-1"></li></ul></div>';
});

describe('project picker', () => {
  it('toggles open and closed, and clears the search when it closes', () => {
    const picker = createProjectPicker();

    picker.toggle();

    expect(picker.isOpen).toBe(true);

    picker.query = 'dem';

    picker.toggle();

    expect([picker.isOpen, picker.query]).toEqual([false, '']);

    picker.toggle();

    picker.close();

    expect(picker.isOpen).toBe(false);
  });

  it('moves the focus down and up between the search field and the options, stopping at both ends', () => {
    const picker = createProjectPicker();

    const [search, first, second] = items();

    search.focus();

    expect(press(picker, 'ArrowDown').defaultPrevented).toBe(true);

    expect(document.activeElement).toBe(first);

    press(picker, 'ArrowDown');

    press(picker, 'ArrowDown');

    expect(document.activeElement).toBe(second);

    press(picker, 'ArrowUp');

    press(picker, 'ArrowUp');

    press(picker, 'ArrowUp');

    expect(document.activeElement).toBe(search);
  });

  it('starts at the search field when the focus is elsewhere, and ignores other keys', () => {
    const picker = createProjectPicker();

    (document.body as HTMLElement).focus();

    press(picker, 'ArrowDown');

    expect(document.activeElement).toBe(items()[0]);

    (document.body as HTMLElement).focus();

    press(picker, 'ArrowUp');

    expect(document.activeElement).toBe(items()[0]);

    expect(press(picker, 'a').defaultPrevented).toBe(false);
  });

  it('does nothing when there is nothing to focus', () => {
    const picker = createProjectPicker();

    container().innerHTML = '';

    expect(press(picker, 'ArrowDown').defaultPrevented).toBe(true);
  });
});
