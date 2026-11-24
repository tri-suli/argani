# Fixtures

`home/` is a minimal argani home with two registered projects: `demo` with three tasks, and `other` with one task (`write-docs`, a draft intent in Backlog), so project filtering is observable. In `demo`: `add-login` has only a draft intent (Backlog), `fix-export` has an approved intent and spec but no build yet (In progress), and `ship-report` went through build, review and decision and has an `mr.md` with a `Merged:` line (Done). Event files are date-named, so tests write them for today's date at run time instead of committing them.
