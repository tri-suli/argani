# argani office

A read-only local dashboard for the argani board: a header with a searchable project picker (task count and tasks waiting for you per project), four totals tiles (agents working, the longest current wait for you, tokens, manual acceptance criteria), a Needs human panel (one row per task, longest wait first, with the reason, question, visit count and a copyable `/argani:factory answer <slug> <answer>` command), a pipeline of five numbered columns (Intake, Spec, Build, Review, Approve, taken from the `column` of each task in `board.json`) whose cards show risk, review chips with state icons, the agent running on the task with its elapsed time, time, tokens and the MR link, a Done rail (merged or cancelled, newest first), and a history and metrics section in the task drawer. IBM Plex Sans, IBM Plex Mono and Material Symbols are bundled with the page (no network at runtime). A small Python backend serves `GET /api/board` (the `board.json` snapshot); the frontend (Alpine.js + TypeScript, built with Vite) polls it every 5 seconds.

Three more read-only endpoints feed the task detail drawer that opens from a card: `GET /api/tasks` (every task with rounds, verdicts, agent time and tokens), `GET /api/tasks/<project>/<slug>` (one task with its file list) and `GET /api/tasks/<project>/<slug>/file?path=<file>` (the text of one listed file, at most 2 MiB). The backend only answers requests whose `Host` is `localhost`, `127.0.0.1` or `[::1]`.

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
