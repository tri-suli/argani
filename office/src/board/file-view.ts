import type { FileGroup, TaskFile } from './types';

/** Groups in order of first appearance ("Job", "Round 1", ...). */
export function groupFiles(files: TaskFile[]): FileGroup[] {
  const groups = new Map<string, TaskFile[]>();
  for (const file of files) {
    groups.set(file.group, [...(groups.get(file.group) ?? []), file]);
  }
  return [...groups].map(([name, members]) => ({ name, files: members }));
}

export function fileName(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1);
}

export function isMarkdownFile(path: string): boolean {
  return path.toLowerCase().endsWith('.md');
}
