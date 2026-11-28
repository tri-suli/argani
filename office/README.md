# argani office

A read-only local dashboard for the argani board: a header with a searchable project picker (task count and tasks waiting for you per project), four totals tiles (agents working, the longest current wait for you, tokens, manual acceptance criteria), a Needs human panel (one row per task, longest wait first, with the reason, question, visit count and a copyable `/argani:factory answer <slug> <answer>` command), a pipeline of five numbered columns (Intake, Spec, Build, Review, Approve, taken from the `column` of each task in `board.json`) whose cards show risk, review chips with state icons, the agent running on the task with its elapsed time, time, tokens and the MR link, a Done rail (merged or cancelled, newest first), and a task page (below). IBM Plex Sans, IBM Plex Mono and Material Symbols are bundled with the page (no network at runtime). A small Python backend serves `GET /api/board` (the `board.json` snapshot); the frontend (Alpine.js + TypeScript, built with Vite) polls it every 5 seconds.

Three more read-only endpoints feed the task page that opens from a card, a Needs human row or a Done rail title: `GET /api/tasks` (every task with rounds, verdicts, agent time and tokens), `GET /api/tasks/<project>/<slug>` (one task with its file list) and `GET /api/tasks/<project>/<slug>/file?path=<file>` (the text of one listed file, at most 2 MiB). 

The task page replaces the board while a task is open and is addressed by the URL hash, `#/task/<project>/<slug>` and, once a file is picked, `#/task/<project>/<slug>/<encoded file path>`: a link opens it directly, the Back button of the browser and "← Board" return to the board at the scroll position it had, with the focus on the element that opened the task, and an unknown task shows a message with a link back. Its header shows the breadcrumb, the title, the column (and the review round while in Review), risk, agent time, tokens, manual acceptance criteria, how often and how long the task needed you, and the merge request. The History strip lists the stages of the task, oldest first, in steps of a fixed width that wrap onto further rows: the time each stayed, the reason of a wait for you, and for each visit to Review the outcome of the matching review round (changes asked or passed) when the board knows it. The file list groups the job files and the review rounds; each round is a button that opens and closes its files, the running round (otherwise the latest one) and the round of the selected file start open. The selected file is shown on the right; a narrow screen puts the file list above it. A markdown file opens in a document reader: its name and a status pill (the `Status:` value, else the verdict first line of a review or decision file), the `# ` title as the reader's heading (the page keeps one h1, so every heading of the document shifts one level down), the `Key: value` lines after the title (`Intent:`, `Spec:`, `Status:`, `Date:`, `Round:`, ... as the templates define them) as a bordered strip, the `## Summary` section as a callout, and the body at a 70-character measure. Fenced code sits in a dark box with its language and a Copy button; tables scroll inside their own box. In the `## Acceptance criteria` section each `n. [ ] <claim> — verify: <how>` item (the shape `artifact_check.py` enforces) is a card with its id (`AC-n`), the claim and the verify command in a mono chip; a `verify: manual: <step>` item gets a manual badge and its step instead. An item that does not have the shape stays a plain list item. "On this page" lists the sections and subsections with the number of criteria and "<words> words · <n> min read"; its entries are buttons that scroll to the section (instantly under reduced motion) and the section being read is highlighted, so the address hash stays the route; in-document links of the markdown scroll the same way. A `.diff` file is a row view with file headers, hunk headers and added and removed lines told apart by colour and by their leading marker; it renders the first 1,500 lines and says how many there are in total. Any other file is shown as plain text. Each open round lists an Overview first (`#/task/<project>/<slug>/round/<n>`): the round on one page with its verdict (the file list's rule: CHANGES, PASS, RUNNING while the latest round is being worked on, otherwise UNDECIDED; the request of the human alone does not decide a round whose reviewers have not all reported) and a sentence made of the verdicts and counts, a Round dropdown (same behaviour as the project picker, without search), one card per review file (verdict, the rest of the first line as headline, "N important · M nits", the model when the task detail names one, a link to the file; `review-human.md` is marked as from the human; a reviewer without a complete file shows as running or not reported), All / Important / Nits chips, and every finding of the round as a card, Important first, with severity, location, reviewer and What / Why / Fix. The findings are read from the `review-<checklist>.md` files by the format of `plugins/argani/docs/review-protocol.md`; a finding that departs from it is still shown whole, with what was recognised and the rest as text (lines that directly follow a bullet belong to it, as in markdown; ordered items and fenced blocks are read too), and every other line of a file is shown as a "Notes from <reviewer>" block under the findings of All, through the same sanitizer (no headings, ids or styles of its own); a link to a fragment in that text does nothing. Code blocks and tables in it scroll inside their own box. A link to a round the task does not have shows the first file.

The backend only answers requests whose `Host` is `localhost`, `127.0.0.1` or `[::1]`.

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
