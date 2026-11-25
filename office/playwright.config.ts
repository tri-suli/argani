import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defineConfig } from '@playwright/test';

const e2eHome = join(tmpdir(), 'argani-office-e2e-home');

const backendPort = 22120;

const deadBackendPort = 22121;

const frontendPort = 22122;

const frontendPortWithDeadBackend = 22123;

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { headless: true },
  projects: [{ name: 'chromium-headless-shell', use: { browserName: 'chromium', channel: 'chromium-headless-shell' } }],
  webServer: [
    {
      command: `node tests/e2e/prepare-home.mjs ${e2eHome} && python3 server/main.py --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/board`,
      env: { ARGANI_HOME: e2eHome },
      reuseExistingServer: false,
    },
    {
      command: `npx vite build && npx vite preview --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
      env: { OFFICE_BACKEND_PORT: String(backendPort) },
    },
    {
      command: `npx vite preview --port ${frontendPortWithDeadBackend}`,
      url: `http://127.0.0.1:${frontendPortWithDeadBackend}`,
      env: { OFFICE_BACKEND_PORT: String(deadBackendPort) },
    },
  ],
});
