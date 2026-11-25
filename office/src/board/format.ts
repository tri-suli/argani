import {
  COUNT_PER_MILLION,
  COUNT_PER_THOUSAND,
  MILLIONS_DISPLAY_THRESHOLD,
  MILLISECONDS_PER_MINUTE,
  MINUTES_PAD_WIDTH,
  MINUTES_PER_HOUR,
  THOUSANDS_DISPLAY_THRESHOLD,
} from '@/board/constants';

/** "12m", "1h05m". */
function formatDuration(milliseconds: number): string {
  const minutes = Math.floor(milliseconds / MILLISECONDS_PER_MINUTE);

  if (minutes < MINUTES_PER_HOUR) {
    return `${minutes}m`;
  }

  return `${Math.floor(minutes / MINUTES_PER_HOUR)}h${String(minutes % MINUTES_PER_HOUR).padStart(MINUTES_PAD_WIDTH, '0')}m`;
}

/** "950", "6.0k", "1.2M". */
function formatCount(count: number): string {
  if (count < THOUSANDS_DISPLAY_THRESHOLD) {
    return String(count);
  }

  return count < MILLIONS_DISPLAY_THRESHOLD ? `${(count / COUNT_PER_THOUSAND).toFixed(1)}k` : `${(count / COUNT_PER_MILLION).toFixed(1)}M`;
}

export { formatDuration, formatCount };
