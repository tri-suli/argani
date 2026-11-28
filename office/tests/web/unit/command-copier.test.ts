import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import createCommandCopier from '@/components/command-copier';

beforeEach(() => vi.useFakeTimers());

afterEach(() => vi.useRealTimers());

describe('command copier', () => {
  it('writes the command to the clipboard and says Copied for a moment, only for that command', async () => {
    const writeText = vi.fn(async () => {});

    const copier = createCommandCopier({ writeText });

    expect(copier.label('a')).toBe('Copy');

    await copier.copy('a', '/argani:factory answer a <answer>');

    expect(writeText).toHaveBeenCalledWith('/argani:factory answer a <answer>');

    expect([copier.label('a'), copier.label('b')]).toEqual(['Copied', 'Copy']);

    vi.advanceTimersByTime(1999);

    expect(copier.label('a')).toBe('Copied');

    vi.advanceTimersByTime(1);

    expect(copier.label('a')).toBe('Copy');
  });

  it('says Copy failed instead of throwing when the clipboard rejects or is missing', async () => {
    const copier = createCommandCopier({ writeText: async () => { throw new Error('denied'); } });

    await expect(copier.copy('a', 'x')).resolves.toBeUndefined();

    expect(copier.label('a')).toBe('Copy failed');

    const missing = createCommandCopier({ writeText: () => { throw new TypeError('no clipboard'); } });

    await missing.copy('a', 'x');

    expect(missing.label('a')).toBe('Copy failed');
  });

  it('restarts the countdown when another command is copied before it ends', async () => {
    const copier = createCommandCopier({ writeText: async () => {} });

    await copier.copy('a', 'x');

    vi.advanceTimersByTime(1500);

    await copier.copy('b', 'y');

    vi.advanceTimersByTime(1500);

    expect([copier.label('a'), copier.label('b')]).toEqual(['Copy', 'Copied']);

    vi.advanceTimersByTime(500);

    expect(copier.label('b')).toBe('Copy');
  });

  it('gives the feedback to the latest click when the writes resolve out of order', async () => {
    const releases: (() => void)[] = [];

    const copier = createCommandCopier({ writeText: () => new Promise<void>((resolve) => releases.push(resolve)) });

    const first = copier.copy('a', 'x');

    const second = copier.copy('b', 'y');

    releases[1]();

    await second;

    releases[0]();

    await first;

    expect([copier.label('a'), copier.label('b')]).toEqual(['Copy', 'Copied']);
  });
});
