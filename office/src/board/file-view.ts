import { MARKDOWN_EXTENSION, PATH_SEPARATOR } from '@/constants/markdown';
import type { TaskFile } from '@/types/task';
import type { FileGroup } from '@/types/view';

/** Groups in order of first appearance ("Job", "Round 1", ...). */
function groupFiles(files: TaskFile[]): FileGroup[] {
  const groups = new Map<string, TaskFile[]>();

  for (const file of files) {
    groups.set(file.group, [...(groups.get(file.group) ?? []), file]);
  }

  return [...groups].map(([name, members]) => ({ name, files: members }));
}

function fileName(path: string): string {
  return path.slice(path.lastIndexOf(PATH_SEPARATOR) + 1);
}

function isMarkdownFile(path: string): boolean {
  return path.toLowerCase().endsWith(MARKDOWN_EXTENSION);
}

export { groupFiles, fileName, isMarkdownFile };
