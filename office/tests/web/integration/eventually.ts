import { vi } from 'vitest';

// vi.waitFor gives up after 1 s by default; on a loaded machine (several suites in parallel) one Alpine render in
// happy-dom alone can take longer, so a passing assertion timed out. A passing check still returns at once.
const EVENTUALLY_TIMEOUT_MILLISECONDS = 10_000;

/** Retries the assertions until they pass, for output that Alpine renders over several ticks. */
const eventually = (assertions: () => void) => vi.waitFor(assertions, { timeout: EVENTUALLY_TIMEOUT_MILLISECONDS });

export default eventually;
