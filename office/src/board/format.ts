import { COUNT_PER_MILLION, COUNT_PER_THOUSAND, MILLIONS_DISPLAY_THRESHOLD, MILLISECONDS_PER_MINUTE, MILLISECONDS_PER_SECOND, MINUTES_PAD_WIDTH, MINUTES_PER_HOUR, SECONDS_PER_MINUTE, SINGULAR_COUNT, THOUSANDS_DISPLAY_THRESHOLD } from '@/constants/format';

/** "12m", "1h05m". */
function formatDuration(milliseconds: number): string {
  const minutes = Math.floor(milliseconds / MILLISECONDS_PER_MINUTE);

  if (minutes < MINUTES_PER_HOUR) {
    return `${minutes}m`;
  }

  return `${Math.floor(minutes / MINUTES_PER_HOUR)}h${String(minutes % MINUTES_PER_HOUR).padStart(MINUTES_PAD_WIDTH, '0')}m`;
}

/** "42s", "12m 05s", "1h 05m": the time since something started, down to the second while it is short. */
function formatElapsed(milliseconds: number): string {
  const seconds = Math.floor(Math.max(0, milliseconds) / MILLISECONDS_PER_SECOND);

  if (seconds < SECONDS_PER_MINUTE) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / SECONDS_PER_MINUTE);

  const pad = (value: number) => String(value).padStart(MINUTES_PAD_WIDTH, '0');

  return minutes < MINUTES_PER_HOUR ? `${minutes}m ${pad(seconds % SECONDS_PER_MINUTE)}s` : `${Math.floor(minutes / MINUTES_PER_HOUR)}h ${pad(minutes % MINUTES_PER_HOUR)}m`;
}

/** "1 task", "2 tasks". */
function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === SINGULAR_COUNT ? '' : 's'}`;
}

/** "950", "6.0k", "1.2M". */
function formatCount(count: number): string {
  if (count < THOUSANDS_DISPLAY_THRESHOLD) {
    return String(count);
  }

  return count < MILLIONS_DISPLAY_THRESHOLD ? `${(count / COUNT_PER_THOUSAND).toFixed(1)}k` : `${(count / COUNT_PER_MILLION).toFixed(1)}M`;
}

export { formatDuration, formatElapsed, formatCount, pluralize };
