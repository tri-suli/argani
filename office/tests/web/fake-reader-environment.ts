import type { ReaderEnvironment, SectionObserver, SectionPosition } from '@/types/document';

class FakeSectionObserver implements SectionObserver {
  observed: Element[] = [];

  disconnected = false;

  constructor(readonly onChange: () => void) {}

  observe(element: Element) {
    this.observed.push(element);
  }

  disconnect() {
    this.disconnected = true;
  }
}

/** A reader environment the test drives: it sets where each heading is, records the observers and says whether motion is reduced. */
class FakeReaderEnvironment implements ReaderEnvironment {
  observers: FakeSectionObserver[] = [];

  positions: Record<string, SectionPosition> = {};

  reducedMotion = false;

  createObserver(onChange: () => void) {
    const observer = new FakeSectionObserver(onChange);

    this.observers.push(observer);

    return observer;
  }

  findElement(id: string) {
    return document.getElementById(id);
  }

  positionOf(id: string) {
    return this.positions[id] ?? 'below';
  }

  prefersReducedMotion() {
    return this.reducedMotion;
  }

  /** Puts the headings where `positions` says, as the reader scrolling would, and tells the observer. */
  move(positions: Record<string, SectionPosition>) {
    Object.assign(this.positions, positions);

    this.latest.onChange();
  }

  get latest() {
    return this.observers[this.observers.length - 1];
  }
}

export default FakeReaderEnvironment;
