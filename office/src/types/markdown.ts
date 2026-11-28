import type { Config, DOMPurify } from 'dompurify';
import type { Token, TokensList } from 'marked';

interface MarkdownSanitizer {
  sanitize: (html: string, options: Config) => string;
}

interface MarkdownParser {
  parse: (markdown: string, options: { async: false }) => string;
  parseInline: (markdown: string, options: { async: false }) => string;
  lexer: (markdown: string) => TokensList;
  parser: (tokens: Token[]) => string;
}

type HookableSanitizer = Pick<DOMPurify, 'addHook'>;

export type { MarkdownSanitizer, MarkdownParser, HookableSanitizer };
