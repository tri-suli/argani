import { describe, expect, it, vi } from 'vitest';
import HashNavigation from '@/board/hash-navigation';

/** A window that records what the adapter does to the address bar. */
function fakeWindow() {
  const listeners = new Map<string, () => void>();

  return {
    location: { hash: '#/task/demo/a', pathname: '/office', search: '?x=1' },
    history: { pushState: vi.fn(), replaceState: vi.fn(), back: vi.fn() },
    addEventListener: vi.fn((type: string, listener: () => void) => listeners.set(type, listener)),
    removeEventListener: vi.fn((type: string) => listeners.delete(type)),
    fire: (type: string) => listeners.get(type)?.(),
    listening: () => listeners.size,
  };
}

describe('hash navigation', () => {
  it('reads the hash', () => {
    expect(new HashNavigation(fakeWindow()).hash()).toBe('#/task/demo/a');
  });

  it('pushes a hash as a history entry and replaces the entry for the board without leaving a bare "#"', () => {
    const browser = fakeWindow();

    const navigation = new HashNavigation(browser);

    navigation.push('#/task/demo/b');

    expect(browser.history.pushState).toHaveBeenCalledWith(null, '', '/office?x=1#/task/demo/b');

    navigation.replace('');

    expect(browser.history.replaceState).toHaveBeenCalledWith(null, '', '/office?x=1');
  });

  it('goes back through the browser history', () => {
    const browser = fakeWindow();

    new HashNavigation(browser).back();

    expect(browser.history.back).toHaveBeenCalled();
  });

  it('tells its listener about Back, Forward and address edits, until stopped', () => {
    const browser = fakeWindow();

    const navigation = new HashNavigation(browser);

    const listener = vi.fn();

    navigation.listen(listener);

    browser.fire('popstate');

    expect(listener).toHaveBeenCalledTimes(1);

    navigation.stop();

    expect(browser.listening()).toBe(0);
  });

  it('has nothing to remove when it was never listening', () => {
    const browser = fakeWindow();

    new HashNavigation(browser).stop();

    expect(browser.removeEventListener).not.toHaveBeenCalled();
  });
});
