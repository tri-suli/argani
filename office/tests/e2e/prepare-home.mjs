// Usage: node prepare-home.mjs <target home>. Copies the fixture home and adds one active agent for today.
import { cpSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const targetHome = process.argv[2];
rmSync(targetHome, { recursive: true, force: true });
cpSync(resolve(import.meta.dirname, '../fixtures/home'), targetHome, { recursive: true });

const now = new Date();
const localDate = [now.getFullYear(), now.getMonth() + 1, now.getDate()].map((part) => String(part).padStart(2, '0')).join('-');
mkdirSync(join(targetHome, 'events'), { recursive: true });
const spawnRecord = {
  ts: now.toISOString().slice(0, 19) + 'Z',
  event: 'spawn',
  session_id: 'e2e-session',
  agent_type: 'argani:builder',
  tool_use_id: 'toolu_e2e_1',
  model: 'sonnet',
  project: 'demo',
  slug: 'fix-export',
  parent_agent_type: null,
  cwd: '/nonexistent/office-fixture-demo',
};
writeFileSync(join(targetHome, 'events', `${localDate}.jsonl`), JSON.stringify(spawnRecord) + '\n');
