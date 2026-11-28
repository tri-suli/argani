// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import createOutlineTracker from '@/components/outline-tracker';
import type { ReaderEnvironment, SectionObserver, SectionVisibility } from '@/types/document';

class FakeObserver implements SectionObserver {
  observed: Element[] = [];

  disconnected = false;

  constructor(readonly onChange: (entries: SectionVisibility[]) => void) {}

  observe(element: Element) {
    this.observed.push(element);
  }

  disconnect() {
    this.disconnected = true;
  }
}

let observers: FakeObserver[];

let reducedMotion: boolean;

const environment: ReaderEnvironment = {
  createObserver: (onChange) => {
    const observer = new FakeObserver(onChange);

    observers.push(observer);

    return observer;
  },
  findElement: (id) => document.getElementById(id),
  prefersReducedMotion: () => reducedMotion,
};

const latest = () => observers[observers.length - 1];

const enter = (id: string) => latest().onChange([{ id, intersecting: true, below: false }]);

const leaveBelow = (id: string) => latest().onChange([{ id, intersecting: false, below: true }]);

const leaveAbove = (id: string) => latest().onChange([{ id, intersecting: false, below: false }]);

beforeEach(() => {
  observers = [];

  reducedMotion = false;

  document.body.innerHTML = '<h3 id="doc-a">A</h3><h3 id="doc-b">B</h3><h3 id="doc-c">C</h3>';

  for (const element of document.querySelectorAll('h3')) {
    element.scrollIntoView = vi.fn();
  }
});

describe('outline tracker', () => {
  it('observes the headings that are in the page and starts at the first section', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b', 'doc-missing']);

    expect(latest().observed.map((element) => element.id)).toEqual(['doc-a', 'doc-b']);

    expect(tracker.activeId).toBe('doc-a');
  });

  it('follows the heading that is in the reading zone, the first one when several are', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b', 'doc-c']);

    enter('doc-c');

    enter('doc-b');

    expect(tracker.activeId).toBe('doc-b');

    leaveAbove('doc-b');

    expect(tracker.activeId).toBe('doc-c');

    leaveAbove('doc-c');

    expect(tracker.activeId).toBe('doc-c');
  });

  it('goes back to the section above when the reader scrolls up past the heading in view', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b', 'doc-c']);

    enter('doc-c');

    leaveBelow('doc-c');

    expect(tracker.activeId).toBe('doc-b');

    leaveBelow('doc-a');

    expect(tracker.activeId).toBe('doc-b');

    tracker.track(['doc-a', 'doc-b', 'doc-c']);

    leaveBelow('doc-b');

    expect(tracker.activeId).toBe('doc-a');
  });

  it('stays on the first section when the reader scrolls back above it', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b']);

    leaveBelow('doc-a');

    expect(tracker.activeId).toBe('doc-a');
  });

  it('ignores a heading that left below when it was not the active one', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b', 'doc-c']);

    enter('doc-b');

    leaveBelow('doc-c');

    expect(tracker.activeId).toBe('doc-b');
  });

  it('keeps the highlight when the same sections are tracked again, and stops observing the old elements', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b']);

    enter('doc-b');

    tracker.track(['doc-a', 'doc-b']);

    expect(observers[0].disconnected).toBe(true);

    expect(tracker.activeId).toBe('doc-b');
  });

  it('forgets the highlight of a section that is gone, and has none without sections', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b']);

    enter('doc-b');

    tracker.track(['doc-a']);

    expect(tracker.activeId).toBe('doc-a');

    tracker.track([]);

    expect(tracker.activeId).toBeNull();
  });

  it('stops observing', () => {
    const tracker = createOutlineTracker(environment);

    tracker.stop();

    expect(observers).toHaveLength(0);

    tracker.track(['doc-a']);

    tracker.stop();

    expect(latest().disconnected).toBe(true);
  });

  it('smooth-scrolls to a section and highlights it at once, instantly under reduced motion', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a', 'doc-b']);

    tracker.scrollTo('doc-b');

    expect(document.getElementById('doc-b')?.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });

    expect(tracker.activeId).toBe('doc-b');

    reducedMotion = true;

    tracker.scrollTo('doc-a');

    expect(document.getElementById('doc-a')?.scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
  });

  it('does not highlight a target that is not an outline section, and ignores a missing one', () => {
    const tracker = createOutlineTracker(environment);

    tracker.track(['doc-a']);

    tracker.scrollTo('doc-b');

    expect(tracker.activeId).toBe('doc-a');

    expect(document.getElementById('doc-b')?.scrollIntoView).toHaveBeenCalled();

    tracker.scrollTo('doc-nothing');

    expect(tracker.activeId).toBe('doc-a');
  });

  describe('in-document links', () => {
    const click = (html: string) => {
      document.body.insertAdjacentHTML('beforeend', html);

      const event = new MouseEvent('click', { bubbles: true, cancelable: true });

      (document.querySelector('[data-test-link]') as HTMLElement).dispatchEvent(event);

      return event;
    };

    it('scrolls to the heading and keeps the route: the click is not left to the browser', () => {
      const tracker = createOutlineTracker(environment);

      document.body.addEventListener('click', (event) => tracker.followAnchor(event));

      const event = click('<a data-test-link data-document-anchor href="#b"><b>inner</b></a>');

      expect(event.defaultPrevented).toBe(true);

      expect(document.getElementById('doc-b')?.scrollIntoView).toHaveBeenCalled();
    });

    it('decodes the fragment, survives a malformed one and prevents the jump either way', () => {
      const tracker = createOutlineTracker(environment);

      document.body.insertAdjacentHTML('beforeend', '<h3 id="doc-é">é</h3>');

      (document.getElementById('doc-é') as HTMLElement).scrollIntoView = vi.fn();

      document.body.addEventListener('click', (event) => tracker.followAnchor(event));

      click('<a data-test-link data-document-anchor href="#%C3%A9">x</a>');

      expect(document.getElementById('doc-é')?.scrollIntoView).toHaveBeenCalled();

      document.querySelector('[data-test-link]')?.remove();

      expect(click('<a data-test-link data-document-anchor href="#%E0%A4%A">x</a>').defaultPrevented).toBe(true);
    });

    it('leaves other clicks alone', () => {
      const tracker = createOutlineTracker(environment);

      document.body.addEventListener('click', (event) => tracker.followAnchor(event));

      expect(click('<a data-test-link href="https://example.test">x</a>').defaultPrevented).toBe(false);

      document.querySelector('[data-test-link]')?.remove();

      expect(click('<p data-test-link>x</p>').defaultPrevented).toBe(false);
    });
  });
});
