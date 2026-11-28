// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import createBrowserReaderEnvironment from '@/board/reader-environment';

class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = [];

  observe = vi.fn();

  disconnect = vi.fn();

  constructor(readonly callback: () => void, readonly options: IntersectionObserverInit) {
    FakeIntersectionObserver.instances.push(this);
  }
}

const fakeWindow = (matches = false) =>
  ({
    IntersectionObserver: FakeIntersectionObserver,
    document,
    innerHeight: 1000,
    matchMedia: vi.fn(() => ({ matches })),
    addEventListener: window.addEventListener.bind(window),
    removeEventListener: window.removeEventListener.bind(window),
    requestAnimationFrame: (callback: () => void) => setTimeout(callback, 0),
  }) as unknown as Window & typeof globalThis;

const heading = (top: number, bottom: number) => {
  document.body.innerHTML = '<h3 id="doc-a"></h3>';

  vi.spyOn(document.getElementById('doc-a') as HTMLElement, 'getBoundingClientRect').mockReturnValue({ top, bottom } as DOMRect);
};

describe('browser reader environment', () => {
  it('watches a reading zone near the top of the page and says when a heading enters or leaves it', () => {
    const onChange = vi.fn();

    const observer = createBrowserReaderEnvironment(fakeWindow()).createObserver(onChange);

    const native = FakeIntersectionObserver.instances[0];

    expect(native.options).toEqual({ rootMargin: '0px 0px -65% 0px' });

    const target = document.createElement('h3');

    observer.observe(target);

    expect(native.observe).toHaveBeenCalledWith(target);

    native.callback();

    expect(onChange).toHaveBeenCalledOnce();

    observer.disconnect();

    expect(native.disconnect).toHaveBeenCalled();
  });

  it('places a heading from where it is on the screen: in the top 35% it is in the zone, above that passed, below that not reached', () => {
    const environment = createBrowserReaderEnvironment(fakeWindow());

    heading(100, 130);

    expect(environment.positionOf('doc-a')).toBe('zone');

    heading(350, 380);

    expect(environment.positionOf('doc-a')).toBe('zone');

    heading(351, 380);

    expect(environment.positionOf('doc-a')).toBe('below');

    heading(-60, -10);

    expect(environment.positionOf('doc-a')).toBe('above');

    heading(-30, 0);

    expect(environment.positionOf('doc-a')).toBe('zone');

    expect(environment.positionOf('doc-missing')).toBe('below');
  });

  it('calls the scroll handler once per frame however many scroll events arrive, until it is stopped', () => {
    vi.useFakeTimers();

    const onScroll = vi.fn();

    const stop = createBrowserReaderEnvironment(fakeWindow()).watchScroll({ onScroll });

    window.dispatchEvent(new Event('scroll'));

    window.dispatchEvent(new Event('scroll'));

    expect(onScroll).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);

    expect(onScroll).toHaveBeenCalledTimes(1);

    window.dispatchEvent(new Event('scroll'));

    vi.advanceTimersByTime(1);

    expect(onScroll).toHaveBeenCalledTimes(2);

    stop();

    window.dispatchEvent(new Event('scroll'));

    vi.advanceTimersByTime(1);

    expect(onScroll).toHaveBeenCalledTimes(2);

    vi.useRealTimers();
  });

  it('finds elements by id and reads the reduced-motion preference when asked', () => {
    document.body.innerHTML = '<h3 id="doc-a"></h3>';

    expect(createBrowserReaderEnvironment(fakeWindow()).findElement('doc-a')).toBe(document.getElementById('doc-a'));

    expect(createBrowserReaderEnvironment(fakeWindow()).findElement('doc-none')).toBeNull();

    expect(createBrowserReaderEnvironment(fakeWindow()).prefersReducedMotion()).toBe(false);

    expect(createBrowserReaderEnvironment(fakeWindow(true)).prefersReducedMotion()).toBe(true);
  });
});
