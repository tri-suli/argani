// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import createBrowserReaderEnvironment from '@/board/reader-environment';

class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = [];

  observe = vi.fn();

  disconnect = vi.fn();

  constructor(readonly callback: (entries: unknown[]) => void, readonly options: IntersectionObserverInit) {
    FakeIntersectionObserver.instances.push(this);
  }
}

const fakeWindow = (matches: boolean) =>
  ({ IntersectionObserver: FakeIntersectionObserver, document, matchMedia: vi.fn(() => ({ matches })) }) as unknown as Window & typeof globalThis;

describe('browser reader environment', () => {
  it('watches a reading zone near the top of the page and reports where a heading left it', () => {
    const environment = createBrowserReaderEnvironment(fakeWindow(false));

    const onChange = vi.fn();

    const observer = environment.createObserver(onChange);

    const native = FakeIntersectionObserver.instances[0];

    expect(native.options).toEqual({ rootMargin: '0px 0px -65% 0px' });

    const target = document.createElement('h3');

    target.id = 'doc-a';

    observer.observe(target);

    expect(native.observe).toHaveBeenCalledWith(target);

    native.callback([
      { target, isIntersecting: true, boundingClientRect: { top: 10 }, rootBounds: { bottom: 300 } },
      { target, isIntersecting: false, boundingClientRect: { top: 400 }, rootBounds: { bottom: 300 } },
      { target, isIntersecting: false, boundingClientRect: { top: -20 }, rootBounds: { bottom: 300 } },
      { target, isIntersecting: false, boundingClientRect: { top: 400 }, rootBounds: null },
    ]);

    expect(onChange).toHaveBeenCalledWith([
      { id: 'doc-a', intersecting: true, below: false },
      { id: 'doc-a', intersecting: false, below: true },
      { id: 'doc-a', intersecting: false, below: false },
      { id: 'doc-a', intersecting: false, below: false },
    ]);

    observer.disconnect();

    expect(native.disconnect).toHaveBeenCalled();
  });

  it('finds elements by id and reads the reduced-motion preference when asked', () => {
    document.body.innerHTML = '<h3 id="doc-a"></h3>';

    expect(createBrowserReaderEnvironment(fakeWindow(false)).findElement('doc-a')).toBe(document.getElementById('doc-a'));

    expect(createBrowserReaderEnvironment(fakeWindow(false)).findElement('doc-none')).toBeNull();

    expect(createBrowserReaderEnvironment(fakeWindow(false)).prefersReducedMotion()).toBe(false);

    expect(createBrowserReaderEnvironment(fakeWindow(true)).prefersReducedMotion()).toBe(true);
  });
});
