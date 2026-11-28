// jsdom ships no types and the project has no @types/jsdom: only what the sample renderer needs
declare module 'jsdom' {
  export class JSDOM {
    constructor(html?: string);

    window: Window & typeof globalThis;
  }
}
