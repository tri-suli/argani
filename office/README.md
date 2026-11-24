# argani office

A read-only local dashboard for the argani board: a kanban of the seven columns, a project filter and the active argani agents. A small Python backend serves `GET /api/board` (the `board.json` snapshot); the frontend (Alpine.js + TypeScript, built with Vite) polls it every 5 seconds.

## Run with Docker

```sh
cp office/.env.example office/.env   # optional: ports and board home
docker compose -f office/compose.yaml up --build
```

Open http://127.0.0.1:1222.

## Run without Docker

```sh
python3 office/server/main.py --port 2212     # ARGANI_HOME selects the board home
npm --prefix office install
npm --prefix office run dev                   # http://127.0.0.1:1222, /api proxied to 2212
```

`OFFICE_FRONTEND_PORT` and `OFFICE_BACKEND_PORT` override the ports.

## Tests

```sh
npm --prefix office run check   # typecheck, vitest (100% coverage), build, Playwright e2e
python3 -m pytest office/tests/server --cov=office/server --cov-branch --cov-fail-under=100
```

First e2e run: `npx --prefix office playwright install chromium-headless-shell`.

- `tests/web/unit`: pure modules (board view, poller with fake timers, fetch client with a fake fetch).
- `tests/web/integration`: real Alpine in happy-dom with a fake client or poller, plus `main.ts`.
- `tests/e2e`: Playwright starts the real backend on a copy of `tests/fixtures/home` and `vite preview` with `/api` proxied to it.
- `tests/server`: backend tests (pytest).
