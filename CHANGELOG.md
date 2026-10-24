# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- MIT license, README, changelog, and `scripts/check.sh` (marketplace and plugin validation plus tests).
- `sdlc` plugin loop reference (`docs/sdlc.md`) and per-repo configuration reference (`docs/config.md`).
- Artifact templates: `intent.md`, `spec.md`, `plan.md`, `build.md`.
- `scripts/sdlc_config.py`: reads `.claude/sdlc.json` from the repository toplevel and merges it over defaults.
- `scripts/artifact_check.py`: slug generation and deterministic checks for `intent.md` and `spec.md`.
- Skills `/sdlc:intent`, `/sdlc:spec`, `/sdlc:plan`, each with an `approve` gate backed by `artifact_check.py status`.
- `plan.md` carries a `Status:` line and is checked by `artifact_check.py plan`; `artifact_check.py status` prints `draft` or `approved` for any valid artifact.
- `sdlc_config.py` fails open: an unusable `.claude/sdlc.json` yields defaults with a note on stderr (the CLI exits 1).
- pytest suites for both scripts.
- Review protocol (`docs/review-protocol.md`): verdict line, findings format, closing line, two-round limit, wait for all, one writer per file, accepted bypasses.
- Checklist catalog: `code`, `security`, `compliance`, `citation`, `format`.
- Checklists `ux` (flows, states, feedback, keyboard access, user-facing copy) and `ui-design` (design-system tokens, component reuse, breakpoints, contrast, themes).
- `PreToolUse` hooks: `guard_git.py` (ask in the main session, deny in subagents for push, merge or pull on the default branch and PR/MR merges) and `guard_artifacts.py` (protected paths, verdict on line 1, round limit, one writer per file).
- pytest suites for both hooks, run as subprocesses with stdin JSON.
- `guard_git.py` parses shell keywords and wrappers (`then`, `do`, `{`, `!`, `time`, `command`, `exec`, `nohup`, `sudo`/`env` options), absolute `git` paths, backticks and `bash|sh|zsh -c` strings, and simulates the current branch through `checkout`/`switch` chains.
- `sdlc:reviewer`, `sdlc:approver` and `sdlc:spec-writer` may write only their own file anywhere in the repository.
- `guard_artifacts.py` asks (main session) or denies (subagent) for writes inside a repository whose `.claude/sdlc.json` is invalid, instead of silently skipping `protectedPaths`.
- Default branch detection falls back to a local `main`, then `master`, then `init.defaultBranch`.
- Agents `spec-writer`, `builder`, `reviewer` (sonnet), `approver`, each writing one artifact.
- Skill `/sdlc:review <slug>`: one parallel reviewer per configured checklist, verdict table, two-round limit.
- Manifest test for agent frontmatter.
- `guard_git.py` enforces a per-agent Bash allowlist (the harness ignores `Bash(...)` scoping in agent `tools`): reviewer and approver run only read-only git without `--output`; spec-writer also runs the plugin's scripts.
- `scripts/factory_state.py <slug>`: read-only JSON report of a job (stage, rounds, partial artifacts, branch, next step), with tests.
- Factory orchestrator commits the job folder on `sdlc/<slug>` (before build, after each round and decision); the builder commits code and `plan.md`/`build.md`.
- Skill `/sdlc:factory <slug>` and `/sdlc:factory rework <slug> <note>`: orchestrator that runs spec, build, review rounds and decision with fresh subagents and stops at the spec gate and the merge request.
- Eval suite (`plugins/sdlc/evals`): `intent-produces-artifact` and `spec-refuses-unapproved-intent`, plus a README and a pytest check that the scaffolded fixtures pass `artifact_check.py`.
- `bootstrap/`: versioned global `CLAUDE.md`, `settings.fragment.json` (marketplace registration only) and an idempotent `install.sh` with `--dry-run`, `--force`, backups and atomic settings merge, with pytest coverage against fake directories.

### Changed

- `docs/sdlc.md` records the behaviour verified in the spike; `docs/config.md` defines `protectedPaths` glob semantics.
