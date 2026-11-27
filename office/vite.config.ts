import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const frontendPort = Number(process.env.OFFICE_FRONTEND_PORT ?? 1222);

const backendPort = Number(process.env.OFFICE_BACKEND_PORT ?? 2212);

const apiProxy = { '/api': `http://127.0.0.1:${backendPort}` };

// above the integration tests' 10 s retry window (tests/web/integration/eventually.ts), so a loaded machine is not a failure
const testTimeoutMilliseconds = 30_000;

export default defineConfig({
  plugins: [tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { host: '127.0.0.1', port: frontendPort, proxy: apiProxy },
  preview: { host: '127.0.0.1', port: frontendPort, proxy: apiProxy },
  test: {
    include: ['tests/web/**/*.test.ts'],
    testTimeout: testTimeoutMilliseconds,
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      reporter: [['text', { skipFull: false }]],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
