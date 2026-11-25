/** "12m", "1h05m". */
function formatDuration(milliseconds: number): string {
  const minutes = Math.floor(milliseconds / 60000);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}m`;
}

/** "950", "6.0k", "1.2M". */
function formatCount(count: number): string {
  if (count < 1000) {
    return String(count);
  }
  // 999_950 would round to "1000.0k"; switch to millions there
  return count < 999_950 ? `${(count / 1000).toFixed(1)}k` : `${(count / 1_000_000).toFixed(1)}M`;
}

export { formatDuration, formatCount };
