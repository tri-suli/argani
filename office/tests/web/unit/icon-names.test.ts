import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ICON, ICON_NAMES } from '@/constants/icons';

const officeRoot = join(import.meta.dirname, '..', '..', '..');

const indexHtml = readFileSync(join(officeRoot, 'index.html'), 'utf8');

const sourceFiles = (directory: string): string[] =>
  readdirSync(directory, { withFileTypes: true }).flatMap((entry) => (entry.isDirectory() ? sourceFiles(join(directory, entry.name)) : [join(directory, entry.name)]));

const typeScriptSources = sourceFiles(join(officeRoot, 'src'))
  .filter((file) => file.endsWith('.ts') && !file.endsWith(join('constants', 'icons.ts')))
  .map((file) => readFileSync(file, 'utf8'));

// the ligature of an icon element is its static text or a quoted name inside its x-text expression
const namesInMarkup = (): string[] =>
  [...indexHtml.matchAll(/<span class="icon\b[^>]*>[^<]*<\/span>/g)].flatMap(([element]) => {
    const staticText = element.replace(/^<[^>]*>/, '').replace(/<\/span>$/, '').trim();

    const expression = /x-text="([^"]*)"/.exec(element)?.[1] ?? '';

    return [staticText, ...[...expression.matchAll(/'([a-z_]+)'/g)].map((literal) => literal[1])].filter(Boolean);
  });

describe('icon names', () => {
  it('lists every name the markup renders, so the committed font subset holds it', () => {
    const missing = namesInMarkup().filter((name) => !ICON_NAMES.includes(name));

    expect(missing).toEqual([]);
  });

  it('lists no name that neither the markup nor the TypeScript uses', () => {
    const inMarkup = new Set(namesInMarkup());

    const unused = Object.entries(ICON).filter(([key, name]) => !inMarkup.has(name) && !typeScriptSources.some((source) => source.includes(`ICON.${key}`)));

    expect(unused).toEqual([]);
  });

  it('is sorted and free of duplicates, the order the font subset is requested in', () => {
    expect(ICON_NAMES).toEqual([...new Set(ICON_NAMES)].sort());
  });
});
