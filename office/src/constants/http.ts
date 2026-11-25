// Shorter than the poll interval: a backend that never answers must surface as a failure, not a hang.
const DEFAULT_TIMEOUT_MILLISECONDS = 4000;

const DEFAULT_POLL_INTERVAL_MILLISECONDS = 5000;

export {
  DEFAULT_TIMEOUT_MILLISECONDS,
  DEFAULT_POLL_INTERVAL_MILLISECONDS,
};
