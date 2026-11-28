import type { Token } from 'marked';

/** The words of inline tokens without their markdown, for a heading's label in the outline. */
function tokenText(tokens: Token[]): string {
  return tokens.map((token) => ('tokens' in token && token.tokens ? tokenText(token.tokens) : 'text' in token ? String(token.text) : '')).join('');
}

export default tokenText;
