import type { Token } from 'marked';
import { TOKEN_HTML } from '@/constants/document';

/** The words of inline tokens without their markdown or html tags, for a heading's label in the outline. */
function tokenText(tokens: Token[]): string {
  return tokens
    .filter((token) => token.type !== TOKEN_HTML)
    .map((token) => ('tokens' in token && token.tokens ? tokenText(token.tokens) : 'text' in token ? String(token.text) : ''))
    .join('');
}

export default tokenText;
