import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/** The real body markup of index.html, without its module script. */
function pageMarkup(): string {
  const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
  const body = /<body[^>]*>([\s\S]*)<\/body>/.exec(html)?.[1] ?? '';
  return body.replace(/<script[\s\S]*?<\/script>/, '');
}

export default pageMarkup;
