// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import createOutlineTracker from '@/components/outline-tracker';
import FakeReaderEnvironment from '../fake-reader-environment';
import type { SectionPosition } from '@/types/document';

let environment: FakeReaderEnvironment;

const move = (positions: Record<string, SectionPosition>) => environment.move(positions);

const trackerOver = (ids: string[]) => {
  const tracker = createOutlineTracker(environment);

  tracker.track(ids);

  return tracker;
};

beforeEach(() => {
  environment = new FakeReaderEnvironment();

  document.body.innerHTML = '<h3 id="doc-a">A</h3><h3 id="doc-b">B</h3><h3 id="doc-c">C</h3>';

  for (const element of document.querySelectorAll('h3')) {
    element.scrollIntoView = vi.fn();
  }
});

describe('outline tracker', () => {
  it('observes the headings that are in the page and starts at the first section', () => {
    const tracker = trackerOver(['doc-a', 'doc-b', 'doc-missing']);

    expect(environment.latest.observed.map((element) => element.id)).toEqual(['doc-a', 'doc-b']);

    expect(tracker.activeId).toBe('doc-a');
  });

  it('follows the first heading in the reading zone, and the last one it has passed when none is', () => {
    const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

    move({ 'doc-a': 'above', 'doc-b': 'zone', 'doc-c': 'zone' });

    expect(tracker.activeId).toBe('doc-b');

    move({ 'doc-b': 'above' });

    expect(tracker.activeId).toBe('doc-c');

    move({ 'doc-c': 'above' });

    expect(tracker.activeId).toBe('doc-c');
  });

  it('settles on the right section after a jump over several, in either direction, and stays on the first above all', () => {
    const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

    move({ 'doc-a': 'above', 'doc-b': 'above', 'doc-c': 'above' });

    expect(tracker.activeId).toBe('doc-c');

    move({ 'doc-a': 'above', 'doc-b': 'below', 'doc-c': 'below' });

    expect(tracker.activeId).toBe('doc-a');

    move({ 'doc-a': 'below' });

    expect(tracker.activeId).toBe('doc-a');
  });

  it('follows a scroll that no heading crossed the edge of the zone for, such as End or a dragged scrollbar', () => {
    const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

    environment.scroll({ 'doc-a': 'above', 'doc-b': 'above', 'doc-c': 'above' });

    expect(tracker.activeId).toBe('doc-c');

    environment.scroll({ 'doc-a': 'zone', 'doc-b': 'below', 'doc-c': 'below' });

    expect(tracker.activeId).toBe('doc-a');
  });

  it('has nothing to release when the scrolling settles without a click', () => {
    const tracker = trackerOver(['doc-a', 'doc-b']);

    environment.positions = { 'doc-a': 'above', 'doc-b': 'zone' };

    environment.settle();

    expect(tracker.activeId).toBe('doc-b');
  });

  it('stops listening to the scroll with the page, and listens again once tracked again', () => {
    const tracker = trackerOver(['doc-a']);

    tracker.stop();

    expect(environment.stoppedScrollWatches).toBe(1);

    tracker.track(['doc-a']);

    expect(environment.scrollHandlers).toHaveLength(2);
  });

  it('keeps the highlight when the same sections are tracked again, and stops observing the old elements', () => {
    const tracker = trackerOver(['doc-a', 'doc-b']);

    move({ 'doc-b': 'zone' });

    tracker.track(['doc-a', 'doc-b']);

    expect(environment.observers[0].disconnected).toBe(true);

    expect(tracker.activeId).toBe('doc-b');
  });

  it('forgets the highlight of a section that is gone, and has none without sections', () => {
    const tracker = trackerOver(['doc-a', 'doc-b']);

    move({ 'doc-b': 'zone' });

    tracker.track(['doc-a']);

    expect(tracker.activeId).toBe('doc-a');

    tracker.track([]);

    expect(tracker.activeId).toBeNull();

    environment.latest.onChange();

    expect(tracker.activeId).toBeNull();
  });

  it('stops observing', () => {
    const tracker = createOutlineTracker(environment);

    tracker.stop();

    expect(environment.observers).toHaveLength(0);

    tracker.track(['doc-a']);

    tracker.stop();

    expect(environment.latest.disconnected).toBe(true);
  });

  it('smooth-scrolls to a section and highlights it at once, instantly under reduced motion', () => {
    const tracker = trackerOver(['doc-a', 'doc-b']);

    tracker.scrollTo('doc-b');

    expect(document.getElementById('doc-b')?.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });

    expect(tracker.activeId).toBe('doc-b');

    environment.reducedMotion = true;

    tracker.scrollTo('doc-a');

    expect(document.getElementById('doc-a')?.scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
  });

  describe('after a click', () => {
    it('keeps the clicked section while it is on its way, and when an earlier one shares the zone with it at the end of the page', () => {
      const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

      tracker.scrollTo('doc-c');

      move({ 'doc-b': 'zone' });

      expect(tracker.activeId).toBe('doc-c');

      move({ 'doc-c': 'zone' });

      expect(tracker.activeId).toBe('doc-c');

      move({ 'doc-b': 'above' });

      expect(tracker.activeId).toBe('doc-c');
    });

    it('follows the reader again once the clicked section has been in the zone and left it', () => {
      const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

      tracker.scrollTo('doc-b');

      move({ 'doc-a': 'above', 'doc-b': 'zone' });

      move({ 'doc-b': 'above', 'doc-c': 'zone' });

      expect(tracker.activeId).toBe('doc-c');
    });

    it('follows the reader when the section was already in the zone at the click and the reader moves on', () => {
      const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

      move({ 'doc-b': 'zone' });

      tracker.scrollTo('doc-b');

      move({ 'doc-b': 'above', 'doc-c': 'zone' });

      expect(tracker.activeId).toBe('doc-c');
    });

    it('keeps a clicked last section that is too short to reach the zone while the page is at its end, and lets go when the reader scrolls back up', () => {
      const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

      tracker.scrollTo('doc-c');

      environment.atPageEnd = true;

      environment.scroll({ 'doc-a': 'above', 'doc-b': 'zone', 'doc-c': 'below' });

      expect(tracker.activeId).toBe('doc-c');

      environment.atPageEnd = false;

      environment.scroll({ 'doc-a': 'zone', 'doc-b': 'below', 'doc-c': 'below' });

      expect(tracker.activeId).toBe('doc-a');
    });

    it('lets go of a click-scroll the reader interrupted once the scrolling has settled', () => {
      const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

      tracker.scrollTo('doc-c');

      environment.scroll({ 'doc-a': 'above', 'doc-b': 'zone' });

      expect(tracker.activeId).toBe('doc-c');

      environment.settle();

      expect(tracker.activeId).toBe('doc-b');
    });

    it('keeps a clicked section that has arrived in the zone when the scrolling settles', () => {
      const tracker = trackerOver(['doc-a', 'doc-b', 'doc-c']);

      tracker.scrollTo('doc-c');

      environment.scroll({ 'doc-b': 'zone', 'doc-c': 'zone' });

      environment.settle();

      expect(tracker.activeId).toBe('doc-c');
    });

    it('lets a new tracking of the page drop the pin', () => {
      const tracker = trackerOver(['doc-a', 'doc-b']);

      tracker.scrollTo('doc-b');

      tracker.track(['doc-a', 'doc-b']);

      move({ 'doc-a': 'zone' });

      expect(tracker.activeId).toBe('doc-a');
    });
  });

  it('does not highlight a target that is not an outline section, and ignores a missing one', () => {
    const tracker = trackerOver(['doc-a']);

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
