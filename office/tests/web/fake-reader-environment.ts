import type { ReaderEnvironment, SectionObserver, SectionVisibility } from '@/types/document';

class FakeSectionObserver implements SectionObserver {
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

/** A reader environment the test drives: it records the observers and says whether motion is reduced. */
class FakeReaderEnvironment implements ReaderEnvironment {
  observers: FakeSectionObserver[] = [];

  reducedMotion = false;

  createObserver(onChange: (entries: SectionVisibility[]) => void) {
    const observer = new FakeSectionObserver(onChange);

    this.observers.push(observer);

    return observer;
  }

  findElement(id: string) {
    return document.getElementById(id);
  }

  prefersReducedMotion() {
    return this.reducedMotion;
  }

  get latest() {
    return this.observers[this.observers.length - 1];
  }
}

export default FakeReaderEnvironment;
