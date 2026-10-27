# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- MIT license, README, changelog, and `scripts/check.sh` (marketplace and plugin validation plus tests).
- `argani` plugin loop reference (`docs/argani.md`) and per-repo configuration reference (`docs/config.md`).
- Artifact templates: `intent.md`, `spec.md`, `plan.md`, `build.md`.
- `scripts/argani_config.py`: reads `.claude/argani.json` from the repository toplevel and merges it over defaults.
- `scripts/artifact_check.py`: slug generation and deterministic checks for `intent.md` and `spec.md`.
- Skills `/argani:intent`, `/argani:spec`, `/argani:plan`, each with an `approve` gate backed by `artifact_check.py status`.
- `plan.md` carries a `Status:` line and is checked by `artifact_check.py plan`; `artifact_check.py status` prints `draft` or `approved` for any valid artifact.
- `argani_config.py` fails open: an unusable `.claude/argani.json` yields defaults with a note on stderr (the CLI exits 1).
- pytest suites for both scripts.
- Review protocol (`docs/review-protocol.md`): verdict line, findings format, closing line, two-round limit, wait for all, one writer per file, accepted bypasses.
- Checklist catalog: `code`, `security`, `compliance`, `citation`, `format`.
- Checklists `ux` (flows, states, feedback, keyboard access, user-facing copy) and `ui-design` (design-system tokens, component reuse, breakpoints, contrast, themes).
- `PreToolUse` hooks: `guard_git.py` (ask in the main session, deny in subagents for push, merge or pull on the default branch and PR/MR merges) and `guard_artifacts.py` (protected paths, verdict on line 1, round limit, one writer per file).
- pytest suites for both hooks, run as subprocesses with stdin JSON.
- `guard_git.py` parses shell keywords and wrappers (`then`, `do`, `{`, `!`, `time`, `command`, `exec`, `nohup`, `sudo`/`env` options), absolute `git` paths, backticks and `bash|sh|zsh -c` strings, and simulates the current branch through `checkout`/`switch` chains.
- `argani:reviewer`, `argani:approver` and `argani:spec-writer` may write only their own file anywhere in the repository.
- `guard_artifacts.py` asks (main session) or denies (subagent) for writes inside a repository whose `.claude/argani.json` is invalid, instead of silently skipping `protectedPaths`.
- Default branch detection falls back to a local `main`, then `master`, then `init.defaultBranch`.
- Agents `spec-writer`, `builder`, `reviewer` (sonnet), `approver`, each writing one artifact.
- Skill `/argani:review <slug>`: one parallel reviewer per configured checklist, verdict table, two-round limit.
- Manifest test for agent frontmatter.
- `guard_git.py` enforces a per-agent Bash allowlist (the harness ignores `Bash(...)` scoping in agent `tools`): reviewer and approver run only read-only git without `--output`; spec-writer also runs the plugin's scripts.
- `scripts/factory_state.py <slug>`: read-only JSON report of a job (stage, rounds, partial artifacts, branch, next step), with tests.
- Factory orchestrator commits the job folder on `argani/<slug>` (before build, after each round and decision); the builder commits code and `plan.md`/`build.md`.
- Skill `/argani:factory <slug>` and `/argani:factory rework <slug> <note>`: orchestrator that runs spec, build, review rounds and decision with fresh subagents and stops at the spec gate and the merge request.
- Eval suite (`plugins/argani/evals`): `intent-produces-artifact` and `spec-refuses-unapproved-intent`, plus a README and a pytest check that the scaffolded fixtures pass `artifact_check.py`.
- `bootstrap/`: versioned global `CLAUDE.md`, `settings.fragment.json` (marketplace registration only) and an idempotent `install.sh` with `--dry-run`, `--force`, backups and atomic settings merge, with pytest coverage against fake directories.

### Changed

- **Breaking:** the plugin `sdlc` is renamed `argani`. Skills are invoked as `/argani:<skill>` and
  agents spawned as `argani:<agent>`. To migrate: reinstall as `argani@argani` instead of
  `sdlc@argani`, rename `.claude/sdlc.json` to `.claude/argani.json`, move `sdlc/<slug>/` folders to
  `argani/<slug>/` (or set `"artifactRoot": "sdlc"`), and rename open `sdlc/<slug>` branches to
  `feature/<slug>` (or set `"branchPattern": "sdlc/{slug}"`).
- The job branch is no longer fixed: `branchPattern` in `.claude/argani.json` sets it, with `{slug}`
  replaced by the job's slug (default `feature/{slug}`). The pattern must contain `{slug}` exactly
  once and give a valid branch name; a pattern that yields a protected branch is refused.
- `defaultBranch` no longer carries every branch role. `baseBranch` (default `defaultBranch`) is where
  job branches start, the merge request target and the base of review diffs (`<baseBranch>...HEAD`);
  `protectedBranches` lists further branches the git guard protects, and the effective list always
  includes `defaultBranch` and `baseBranch`. This supports Git Flow (`baseBranch: "develop"`, with
  `main` and `develop` both protected). Agent prompts carry `Base branch` instead of `Default branch`,
  and the factory state reports `base_branch` and `protected_branches` instead of `default_branch`.
- `docs/argani.md` records the behaviour verified in the spike; `docs/config.md` defines `protectedPaths` glob semantics.
- `/argani:factory` given a description instead of a slug (or a slug with no job folder) stops and
  points to `/argani:intent`, instead of improvising; an empty argument prints the usage. The skill and
  `docs/argani.md` state that invoking the factory is the explicit instruction for the commits it makes,
  and that repositories requiring a separate instruction per commit should use the manual loop.
- Factory commit messages are configurable: `recordCommitMessage` (default
  `chore(argani): record {slug} {what}`) sets the subject of the orchestrator's record commits, and
  `commitTrailers` (default `[]`) adds git trailers such as `Co-Authored-By` to every orchestrator and
  builder commit. Both were hardcoded (`chore(argani)`, no trailers), which repositories with a
  commitlint scope list or a required trailer rejected.
- `guard_artifacts.py` checks `protectedPaths` through symlinks: a protected folder that is a symlink
  to a folder outside any repository (for example shared sources in a worktree) was written without a
  check; it is now matched as written in the repository that holds the symlink.
- `guard_git.py` closes gaps found in review of the protected-branch change: a `switch`/`checkout` to
  a branch that exists only on a remote (or via `--track origin/<branch>`) is followed, and an
  undeterminable switch (`-`, a commit) holds later pushes, merges and pulls; `heads/<branch>` push
  destinations are matched; an invalid `.claude/argani.json` now holds every push, merge and pull
  instead of falling back to defaults. Branch names in the config are trimmed, lose `refs/heads/`,
  and must be valid and not remote-prefixed; `protectedBranches` accepts globs such as `release/*`.
  Follow-up from a second review: create flags written attached or clustered (`-bdevelop`,
  `-fb develop`, `--create=develop`, `--orphan`) are followed; `checkout <tree-ish> -- <paths>` no
  longer counts as a branch switch; an unreadable `.claude` directory holds pushes instead of
  crashing open; `heads/` is dropped from configured names, and other `refs/` names and `@{...}`
  are rejected.
  Follow-up from a third review, which found the branch simulation could still be bypassed:
  subagents are now denied every push, pull, merge and send-pack on any branch, checked on the
  de-quoted words of the whole command (quoting, `bash -c`, substitutions, wrappers, `eval`,
  `-c alias.*` and repository aliases that push or run a shell are caught); the message of
  `git commit -m` is not scanned. The main-session simulation follows clustered create flags with
  an attached name (`-fBdevelop`) and skips option values (`--conflict merge`). `baseBranch: "@"`
  is rejected. After a fourth review: only commands that name a git tool are scanned, and existing
  paths (`src/push.ts`) and `git stash push` are not, so `docker pull`, `grep pull` and linting
  `merge.ts` work again; a shell reading a pipe or heredoc, `eval`/`source` of generated text,
  and command substitutions in shell code or git commands are denied, closing encoded commands
  such as `bash -c "git $(echo hsup | rev) ..."`. After a fifth review: the `git stash push`
  exemption applies only to the parsed `stash` subcommand (`git -C stash push` was allowed), a
  glob in the program (`/usr/bin/g[i]t`) counts as a git tool, shells reading `-`, `/dev/stdin`
  or `-s` and shells run through `busybox`, `toybox` or `xargs` are denied, and the heredoc body
  of `git commit -F -` is treated as a message.
- `bootstrap/install.sh` no longer runs `claude plugin marketplace list`, which could not show `argani` before the next session; it checks that `settings.json` registers `argani` and says the marketplace is cloned when the next session starts.
- `bootstrap/install.sh` copies `claude/CLAUDE.md` to both global locations instead of symlinking them, so the global configuration no longer depends on the checkout; symlinks from an earlier install are replaced by copies, and the worktree refusal is dropped.
- Checklist `code` reports opaque or inconsistent names (internal labels such as `a1`, or names that differ from those set by the spec, plan or existing code) as Important.
- Agents `builder` and `spec-writer` follow a naming rule: reuse names from the spec, intent and repository; new names are descriptive and stay consistent; no internal labels such as `a1` or `round2`.
- `artifact_check.py intent` rejects acceptance criteria whose `verify:` is a filler (`TBD`, `TODO`, `N/A`, `?`, ...) or an empty code span, so such an intent cannot be approved.
