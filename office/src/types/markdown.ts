import type { Config, DOMPurify } from 'dompurify';

interface MarkdownSanitizer {
  sanitize: (html: string, options: Config) => string;
}

interface MarkdownParser {
  parse: (markdown: string, options: { async: false }) => string;
}

type HookableSanitizer = Pick<DOMPurify, 'addHook'>;

export type { MarkdownSanitizer, MarkdownParser, HookableSanitizer };
