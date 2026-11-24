import { defineConfig } from 'vitest/config';

const frontendPort = Number(process.env.OFFICE_FRONTEND_PORT ?? 1222);
const backendPort = Number(process.env.OFFICE_BACKEND_PORT ?? 2212);
const apiProxy = { '/api': `http://127.0.0.1:${backendPort}` };

export default defineConfig({
  server: { host: '127.0.0.1', port: frontendPort, proxy: apiProxy },
  preview: { host: '127.0.0.1', port: frontendPort, proxy: apiProxy },
  test: {
    include: ['tests/web/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      reporter: [['text', { skipFull: false }]],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
