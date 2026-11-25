// Usage: node prepare-home.mjs <target home>. Copies the fixture home and adds today's events: one active agent and one finished builder.
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

const finishRecord = {
  ts: now.toISOString().slice(0, 19) + 'Z',
  event: 'finish',
  session_id: 'e2e',
  agent_type: 'argani:builder',
  tool_use_id: 'e2e-finish-1',
  agent_id: 'e2e-agent',
  status: 'completed',
  parent_agent_type: null,
  duration_ms: 125000,
  project: 'demo',
  slug: 'ship-report',
  usage: { input_tokens: 1200, output_tokens: 800, cache_creation_input_tokens: 0, cache_read_input_tokens: 4000 },
};

writeFileSync(join(targetHome, 'events', `${localDate}.jsonl`), [spawnRecord, finishRecord].map((record) => JSON.stringify(record)).join('\n') + '\n');
