---
type: llm
focus:
  source: file
  path: sdlc/demo-login/intent.md
---
You are given the intent.md that the assistant wrote. PASS only if all of the following hold, otherwise FAIL:
1. Every acceptance criterion names a concrete verification method (a command, a test, or a named manual step), not a vague phrase such as "works well".
2. The sections Problem, Desired outcome, Affected users and systems, Constraints, Acceptance criteria, Out of scope and Open questions are all present and filled in (no leftover template placeholders such as `<problem>`; HTML comments from the template are ignored when judging leftover placeholders).
3. The prose is written in one language throughout (file names, `Status:`, `AC-n` and `verify:` stay English by design and do not count).
