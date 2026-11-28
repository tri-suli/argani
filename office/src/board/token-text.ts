import type { Token } from 'marked';

const ENTITIES: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'" };

const ENTITY_PATTERN = /&(?:amp|lt|gt|quot|#39);/g;

/** The words of inline tokens without their markdown, for a heading's label in the outline. */
function tokenText(tokens: Token[]): string {
  const text = tokens.map((token) => ('tokens' in token && token.tokens ? tokenText(token.tokens) : 'text' in token ? String(token.text) : '')).join('');

  return text.replace(ENTITY_PATTERN, (entity) => ENTITIES[entity]);
}

export default tokenText;
