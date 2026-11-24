/** happy-dom keeps the class attribute stale after Alpine's classList updates; the serialized tag is accurate. */
export function classesOf(element: Element | null): string[] {
  const html = element?.outerHTML ?? '';
  return /^[^>]*?\sclass="([^"]*)"/.exec(html)?.[1].split(/\s+/) ?? [];
}

export const hasClass = (element: Element | null, name: string) => classesOf(element).includes(name);
