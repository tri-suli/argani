import { COMMENT_PATTERN, MINIMUM_READ_MINUTES, WHITESPACE_PATTERN, WORDS_PER_MINUTE } from '@/constants/document';

/** Words outside HTML comments (the templates carry instructions in them) and the minutes they take to read. */
function readingStats(text: string): { words: number; minutes: number } {
  const words = text.replace(COMMENT_PATTERN, ' ').split(WHITESPACE_PATTERN).filter((word) => word !== '').length;

  return { words, minutes: Math.max(MINIMUM_READ_MINUTES, Math.ceil(words / WORDS_PER_MINUTE)) };
}

export default readingStats;
