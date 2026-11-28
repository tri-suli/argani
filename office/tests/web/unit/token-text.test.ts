import { marked } from 'marked';
import { describe, expect, it } from 'vitest';
import tokenText from '@/board/token-text';

const inline = (markdown: string) => (marked.lexer(`# ${markdown}`)[0] as { tokens: Parameters<typeof tokenText>[0] }).tokens;

describe('token text', () => {
  it('keeps the words of nested inline markdown and none of the html tags around them', () => {
    expect(tokenText(inline('**Bold** and `a<b` & [link](https://example.test) <i>x</i>'))).toBe('Bold and a<b & link x');
  });

  it('gives a token without text, or with only nested tokens, no text of its own', () => {
    expect(tokenText([{ type: 'space', raw: '\n' }])).toBe('');

    expect(tokenText([{ type: 'em', raw: '*a*', text: 'a', tokens: [] }])).toBe('');
  });
});
