# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.0] - 2026-10-30

### Added

- `/argani:factory <slug> [in <dir>]`, `/argani:factory rework <slug> [in <dir>] <note>` and `/argani:review <slug> [in <dir>]`: `in <dir>` names the working directory of the job; without it the session directory stays the default. Every script call of both skills carries it.
- `Working directory:` line in the builder prompt; the builder runs every command there.
- `mr_description.py` prints `directory` (the real path of the working directory) and its `command` starts with `cd` into it.

### Fixed

- A session started outside the job's checkout, for example the main checkout with worktrees under `.worktrees/`, can run the factory and the review without a new session. A working directory nested inside the registered path (for example `.worktrees/<slug>`) must be covered by a `paths` pattern in `project.json` (see `docs/config.md`, 2.1.0), otherwise the project root is the outer checkout and `diffCommand` and `protectedPaths` use the wrong root.
- `factory_state.py` exits 1 and `argani_config.py` exits 2 when the directory argument is not a directory; the state JSON has `directory`, the real path of the working directory.

### Changed

- The `command` of `mr_description.py` starts with `cd <directory> && ( ... )` even without `in <dir>`; the parentheses keep a `||` or `;` inside `mrCommand` from running after a failed `cd`.

## [2.1.0] - 2026-10-29

### Added

- An entry of `paths` in `project.json` may be a pattern (`*` and `?` stay inside one path segment; there is no `**`), for example `/p/app/.worktrees/*`. The nearest ancestor of a directory that equals or matches an entry is the project root. Patterns are added by hand.

### Changed

- `register_project.py` skips the inside/contains checks for pattern entries, so the literal parent can be registered while the project lists a pattern under it. It refuses a directory that a pattern of another project matches or whose subtree holds that pattern, naming the pattern and the project, and a directory whose own name holds `*` or `?`.
- `read_project` strips a trailing `/` from each `paths` entry.

### Fixed

- In checkouts nested inside a registered path (for example worktrees under `.worktrees/`), `diffCommand` ran in the outer checkout and printed nothing, and `protectedPaths` were matched against the outer root. List the nested checkouts as a pattern in `paths`.

## [2.0.0] - 2026-10-29

argani no longer runs git. It is a local board for every project (the argani home, `projects/<name>/project.json`, `tasks/<slug>/`, the factory loop, the agents, `/argani:board`); branches, worktrees, commits, pushes and merges are the project's own business, done with its own rules and skills.

### Removed

- The git guard: `hooks/guard_git.py`, its `hooks.json` entry and its four test files. argani no longer holds pushes or merges and has no per-agent Bash allowlist; the reviewer and the approver now have no `Bash` at all.
- `scripts/git_cli.py`, `scripts/next_number.py`, `scripts/worktree_command.py` and `scripts/merge_command.py`, with their tests.
- Config keys `defaultBranch`, `baseBranch`, `protectedBranches`, `branchPattern`, `branchTypes`, `baseBranchByType`, `branchNumberCommand`, `worktreePath`, `worktreeCommand`, `mergePolicy`, `mergeCommand`, `commitTrailers` and `commitSkill`, their coercers and cross-key rules, and the `mrCommand` placeholders `{branch}` and `{base}` (only `{title}` and `{bodyFile}` remain). A leftover key in a `project.json` is ignored with a note on stderr.
- The intent header lines `Type:` and `Number:` (and their template lines and checks): the intent check needs no config any more. `Risk:` stays.
- Project identity by git remote: `project.json` keeps `name` and `paths` only (a leftover `remotes` key is tolerated and ignored). `normalize_remote`, `repository_remotes`, `main_checkout` and `toplevel` are gone; a project is found by the real path of a directory or of its nearest registered ancestor.
- From the factory state: `branch`, `current_branch`, `on_job_branch`, `dirty`, `base_branch`, `type`, `number`, `worktree_*`, `checkout`, `main_checkout`, `record_dir`, `records_enabled`, `merge_policy`, `protected_branches`. The factory has no branch step, no record commits, no push and no merge: `done` is terminal. The builder prompt is `Plugin root`, `Slug folder`, `Verify command`, `Round` and `Findings to address` only.
- The board no longer reads branches or checkouts: a finished task is Done only when `mr.md` has a valid `Merged: <date>` line. `import_jobs.py` reads the working tree only (a job that lives only on a branch must be checked out first) and no longer records the import in the home. `argani_home.py` no longer reports `git`.

### Added

- `diffCommand` (required by the factory and the review, like `verifyCommand`): the project's command that prints the change under review as a unified diff. It must match the project's commit rule for the builder: `git diff origin/main...HEAD` shows committed work only, `git diff origin/main` shows the working tree but not untracked files (a project that forbids agent commits needs a working-tree diff, and new files need `git add -N` to appear). `/argani:init` offers both.
- `scripts/capture_change.py <slug> [dir]`: runs `diffCommand` (shell, with the project root as working directory, 120 s limit with the whole process group killed on timeout, stdin closed, output kept byte for byte as UTF-8) and writes it to `review/round-<N>/change.diff` for the next review round, printing `{"path", "bytes", "files"}`. It refuses to replace the `change.diff` of a round that already holds a review ("round N already has reviews; the change is fixed for that round"), warns on stderr above 1 MB and when nothing was printed (check `diffCommand` against the builder's commit rule). At `needs-decision` it fills a missing `change.diff` of a round reviewed before 2.0.0. The factory and `/argani:review` run it before spawning reviewers; the reviewer and the approver read `Change: <round folder>/change.diff`. An empty diff stops with "diffCommand printed nothing; nothing to review".
- `reviewerPaths` now selects reviewers from the files named in the latest round's `change.diff`; without one, every reviewer runs.
- `change.diff` is written by `capture_change.py` alone: the guard denies `Write` and `Edit` of it to every caller, the main session and other plugins' subagents included. Writes through `Bash` are not guarded (the builder has full `Bash` and is told not to touch the task folder except `plan.md` and `build.md`).
- A round's reviewers are the ones `reviewerPaths` selects from its `change.diff` plus every reviewer that said `CHANGES` in the round before, so a finding is always checked again. `diff_files` gives up (every reviewer runs) when a `diff --git` line cannot be read with certainty (quoted paths, non-standard prefixes, `" b/"` inside a path).
- `register_project.py` refuses a directory that is inside or contains a registered path of any project, the same project included.
- `register_project.py <name> <dir>` registers `realpath(dir)` of any directory, no git needed, and appends the path when the same project is registered again from another directory.
- `/argani:init` asks for `diffCommand` and proposes both the `gh` and the `glab` form for `mrCommand`; the project name comes from the folder name and is always confirmed.

### Changed

- `argani_config.load_config()` stays quiet about leftover keys of a `project.json` (hooks run it on every tool call): the names are in `config["ignoredKeys"]` and only `argani_config.py` on the command line prints the note.
- The builder prompt lists the review files to address, one path per file (`Findings to address:` followed by one path per line), not a folder.
- `argani_config.load_config()` returns `projectRoot` (the registered path that contains the directory) instead of `toplevel` and `currentBranch`; the artifact guard uses it for `protectedPaths`. `validate_overrides()` only checks that `reviewerPaths` names listed reviewers.
- `read_legacy_file()` coerces `artifactRoot` only; removed keys of an old `.claude/argani.json` are dropped by `/argani:init` and reported in `legacyUnknownKeys`.
- `mr_description.py` writes no branch lines; its argani section names the task only.
- The approve steps of the intent, spec and plan skills take the approver's name from the user instead of `git config user.name`.
- `/argani:review` takes the round number from the factory state and refuses a job that has no round waiting.
- Docs rewritten: `config.md`, `argani.md` (with a "What argani does not do" section), `review-protocol.md`; the spec eval scaffold no longer runs `git init`.

### Migration

- Drop the removed keys from each `project.json` (they are ignored, but stale) and set `diffCommand`, for example `git diff origin/main...HEAD` for a project that works on branches off `main`.
- Prepare branches and worktrees with your own tools (and commit with your own rules and skills) before `/argani:factory`, and start the session in the directory where the work is; the builder follows the project's `CLAUDE.md` for commits.
- Open and merge merge requests yourself; add `Merged: <YYYY-MM-DD>` to `mr.md` when merged, which is what marks the task Done on the board.
- Remove the `Type:` and `Number:` lines from existing intents if you like; they are no longer checked.
- Rounds reviewed before 2.0.0 have no `change.diff`; at `needs-decision` run `python3 <plugin>/scripts/capture_change.py <slug>` to fill it (the factory does it before the approver), or the approver has no change to read.
- Jobs merged under 1.x need a line `Merged: <YYYY-MM-DD>` in their `mr.md` to show Done on the board: argani no longer looks at branches.
- `project.json` entries that have `remotes` but no `paths` can no longer be found: re-register the directory with `/argani:init`.

## [1.0.0] - 2026-10-29

### Removed

- The per-repository mode: `.claude/argani.json` is no longer read as a config source, so a repository without a registered project has no job folder. The keys `artifactRoot` and `recordCommitMessage` and `argani_config.record_commit_message()` are gone; record commits in the repository and the `job_dir_in_repo` field of the factory state are gone with them (the job folder is always in the argani home, `record_dir` is always the home and the orchestrator records only when the home is a git repository of its own). The builder never commits `plan.md` or `build.md`. `next_number.py` no longer scans branches for intents: the tasks source is the project's task folders. The artifact guard no longer knows artifact paths inside a repository: there it applies only `protectedPaths` and the one-writer rule (the reviewer, approver and spec-writer may write nothing in a repository).

### Changed

- An unregistered repository gets the default config plus the detected branches, `tasksDir` is `null`, and any script that loads the config prints one stderr line when `.claude/argani.json` exists: `argani: .claude/argani.json is no longer read since 1.0.0; run /argani:init to register this repository (its keys are carried over)`. `factory_state.py` and `mr_description.py` exit 1 with `This repository is not registered; run /argani:init`, and `/argani:intent`, `/argani:spec` and `/argani:plan` stop. `worktreePath` no longer needs a registered project check, since every job has one.
- `argani_config.read_legacy_file(path)` validates an old `.claude/argani.json` (the current keys plus `artifactRoot` and `recordCommitMessage`); only `/argani:init` (carry-over) and `/argani:import` (`artifactRoot`) still read it.
- Hooks in a repository that is not registered: `protectedPaths`, `protectedBranches`, `baseBranch` and `mergePolicy` from `.claude/argani.json` are no longer enforced until `/argani:init` runs (only the detected default branch stays protected), and a broken `.claude/argani.json` no longer holds pushes or asks on writes, because it is ignored.
- The spec eval case was updated to the hub layout and passes in the sandbox (its scaffold registers the repository in `$ARGANI_HOME`, else `~/.argani` of the sandbox, writes that path to `.argani-home-path` and links it as `.argani-home` for the graders). The `intent-produces-artifact` eval case is removed: the sandbox home is read-only outside the working directory, so a case that writes into the argani home cannot run there.
- Without git (missing or masked), a folder is matched to a project by the registered `paths` of itself or its nearest registered ancestor; `argani_config.py` then reports the project and `tasksDir` with `toplevel` and `currentBranch` null.

### Migration

Run `/argani:init` in each repository that used `.claude/argani.json` (its keys are carried over) before relying on the upgraded plugin there, in particular where `protectedPaths` or `protectedBranches` were set; then `/argani:import` to move the old job folders (`argani/<slug>`) into the argani home, and afterwards delete the old folders and `.claude/argani.json` through the repository's normal process (a branch, a commit, a merge request). argani never deletes them.

## [0.21.0] - 2026-10-29

### Added

- `/argani:import [<slug> ...]` and `scripts/import_jobs.py [dir] [--slug <slug> ...] [--artifact-root <folder>] [--apply]`: copies the legacy job folders (`<artifactRoot>/<slug>/`, found in the working tree and on every local and remote branch) of a registered repository to the project's task folder in the argani home. The plan is printed first (source and reason, candidates with `differs`, files, skipped links, status); `--apply` copies, compares each written file with the bytes read from its source, reports the stage of each job and, when the home is a git repository, records the import there. A rerun reports `already-imported`; a destination with different or extra files is a `conflict` and is never written. The repository is never modified.

## [0.20.0] - 2026-10-29

### Added

- `mergePolicy` (`human` default, or `agent`) and `mergeCommand` (placeholders `{branch}`, `{base}`, `{mr}`; required by `agent`). With `agent`, the git guard no longer holds a merge request merge (`gh pr merge`, `glab mr merge`, the API merge paths) or a `git merge` on a protected branch, for the main session and subagents; a direct push to a protected branch stays held under both policies and the reviewer, approver and spec-writer allowlist is unchanged. After `APPROVE` the factory opens the merge request, runs the command printed by the new `scripts/merge_command.py <slug> [dir]` (the merge request URL or `!n`/`#n` is read from `mr.md`) and appends `Merged: <date>` to `mr.md`. The factory state reports `merge_policy` and `mr.merged`. `/argani:init` asks for both keys.

### Changed

- A task is Done on the board when `mr.md` has a `Merged: <YYYY-MM-DD>` line, or when its branch is merged in a local checkout as before. The `done` stage under `agent` with an unmerged `mr.md` tells the factory to run the merge step.

## [0.19.0] - 2026-10-28

### Added

- Worktree mode: `worktreePath` (a folder with `{branch}` once, for example `.worktrees/{branch}`) makes the factory run every job in its own git worktree and never switch branches in the main checkout; `worktreeCommand` optionally creates the worktree (placeholders `{branch}`, `{base}`, `{path}`), else argani runs `git worktree add`. New `scripts/worktree_command.py <slug>` prints the filled command. The factory state gains `worktree_mode`, `worktree_path` and `checkout`; `current_branch`, `on_job_branch` and `dirty` describe the checkout, and the top folder of `worktreePath` never makes the main checkout dirty. Every git command of a job, `mr_description.py` and the builder, reviewer and approver prompts (`Checkout:`) use the checkout. Only for a registered project. `/argani:init` asks for `worktreePath` when the repository already uses worktrees. `checkout`, `current_branch` and `dirty` are null before the worktree exists; `/argani:review` then says the job has no worktree yet. A project registered by `paths` resolves from its linked worktrees (through the path of the main checkout), worktree mode is anchored on the main checkout whichever worktree runs the scripts, a stale (prunable) worktree is reported instead of used, and `worktreeCommand` has a `{toplevel}` placeholder. The reviewer and approver agents may also call `git -C`; the git guard still allows only read-only subcommands.

## [0.18.0] - 2026-10-28

### Added

- Job number in the branch name: `branchPattern` may contain `{n}` once (`feat/common-{n}-{slug}`). The number is assigned once by `/argani:intent` and stored in the intent as a `Number: 56` header line; `artifact_check.py` requires it when the pattern has `{n}`, and the factory state reports it as `number`. `scripts/next_number.py` prints the next number: from the new `branchNumberCommand` (a shell command that prints it, for a project with its own registry) or one more than the highest `Number:` of the project's intents. `/argani:init` offers an `{n}` candidate when existing branches carry a number, and asks for `branchNumberCommand`. The `tasks` source counts only intents that exist (a registered project: its task folders; a legacy repository: the working tree and every local and remote branch), so two intents written at the same time can get the same number and a registry command is the safe choice for teams; deleting an intent frees its number. Migration: adding `{n}` to an existing project makes running jobs invalid until their intent gets a `Number:` line, and their branch name changes. The last non-empty line of `branchNumberCommand` output must be a positive integer.

## [0.17.0] - 2026-10-28

### Changed

- argani no longer initialises a git repository in the argani home: `argani_home.py --create` and project registration make folders only, and the `git` field of the output is informational. The factory records job folders as commits only when the user has made the home a repository of its own (`records_enabled` in the factory state replaces `record_repo_ok`); otherwise the artifacts stay as files and nothing is committed. A home created by 0.13.0-0.16.0 keeps its `.git`, which the user may delete.
- Interface: the `git` field of `argani_home.py` now means "a repository of its own" (it used to mean `.git` exists), and `record_repo_ok` is gone from the factory state.

## [0.16.0] - 2026-10-28

### Added

- `mr_description.py` generates the merge request title and description of a job: the summary, the acceptance criteria of the intent, the human verification checklist of the decision and the location of the task folder. `--write` saves the body as `<job_dir>/mr-body.md` and adds `bodyFile` and, when `mrCommand` is set, `command` (placeholders replaced by shell-quoted values) to the JSON. `artifact_check.acceptance_criteria` returns the criteria of an intent.

### Changed

- `mrCommand` accepts the placeholders `{branch}`, `{base}`, `{title}` and `{bodyFile}` and rejects any other, quoted placeholders, an empty value and a multi-line value; the shell quoting is done by `mr_description.py`, not the agent. `${VAR}` is no longer read as a placeholder. `/argani:init` proposes `gh pr create` / `glab mr create` with `--title` and a description file instead of `--fill`, so the merge request states what to verify. The factory generates the description before pushing; without `mrCommand` it prints the title and the description file.

## [0.15.0] - 2026-10-28

### Added

- Skill `/argani:board [--all]` shows the board of this repository's project, or of every project, by column. It runs `board.py` and writes nothing.

## [0.14.0] - 2026-10-28

### Added

- `board.py` lists the tasks of the registered projects in the columns Backlog, Design, In progress, Ready for MR, In review, Done and Needs human, derived from the stage and from whether the job branch is merged. `--all` covers every project, `--write` saves `<home>/board.md`, `--json` prints the board as JSON. `build_state` takes `with_working_tree=False` to skip the working-tree git calls.

## [0.13.0] - 2026-10-28

### Added

- The argani home is a git repository: `argani_home.py --create` runs `git init` when it is not one yet (never touching an existing repository) and reports `git`.
- `factory_state.py` reports `project`, `home`, `record_dir` and `job_dir_in_repo`, and `build_state` accepts a config so the board can read a job without a checkout (`current_branch` and `dirty` are then null).

### Changed

- `/argani:factory` and `/argani:review` find the job folder through `job_dir` from the state, so they work on the board. For a registered project the orchestrator records the job folder in the argani home's git repository with the fixed message `argani: record <project>/<slug> <what>`, independent of the project repository's branch.
- The builder commits `plan.md` and `build.md` only when the prompt says `Job folder in repository: yes`.
- `recordCommitMessage` is legacy only: `register_project.py` refuses it and `/argani:init` does not carry it over.
- The "No job folder" message names the tasks folder and suggests `git switch` only for a legacy repository.

## [0.12.0] - 2026-10-28

### Changed

- `/argani:intent`, `/argani:spec` and `/argani:plan` write the artifacts to `tasksDir` from `argani_config.py`: the task folder in the argani home for a registered project (nothing is written into the repository), `<artifactRoot>/<slug>/` in the repository otherwise. Outside a git repository they stop and point to `/argani:init`.
- `/argani:review` and `/argani:factory` still look for the job folder in the repository; they follow in the next release.

## [0.11.0] - 2026-10-28

### Added

- `guard_artifacts.py` applies the writer, round and verdict rules to the task folders of the argani home
  (`<home>/projects/<name>/tasks/<slug>/`) and explicitly allows the writes that pass, in the main
  session and in subagents, which also spares the permission prompt for writes outside the working
  directory. `protectedPaths` are not checked there.
- `hook_common.emit_allow` prints an explicit allow decision; `argani_config.SLUG_PATTERN` is shared with `factory_state.py`.

### Changed

- Only a proper artifact path `tasks/<slug>/<file>` (valid slug, no dotted part) is allowed explicitly;
  other paths under `projects/<valid name>/` get no decision and sole-file writers are denied there.
  The home is not treated as a legacy repository for paths under `projects/<valid name>/`; other paths
  in the home still take the ordinary flow. `protectedPaths` through a repository symlink into the hub
  are still enforced. Inside the hub an unverifiable verdict edit is denied. Guard messages refer to "the project's configuration" instead of `.claude/argani.json`.

## [0.10.0] - 2026-10-28

### Added

- `scripts/register_project.py <name> [dir] < config.json` creates or extends
  `projects/<name>/project.json` in the argani home from the repository and the validated config on
  stdin. It refuses a name or remote that another project holds and never writes into the repository.
- `init_config.py` reports the hub target: `project`, `remotes`, `realPath`, `home`, `projectFile`,
  `registered`, `homeError`, and the carried-over `legacyKeys` of an existing `.claude/argani.json`.

### Changed

- `argani_config.validate_overrides` holds the cross-key and remote-prefix checks shared by
  `load_config` and `register_project.py`; `LEGACY_ONLY_KEYS` names `artifactRoot`.
- `/argani:init` registers the repository as a project in the argani home instead of writing
  `.claude/argani.json`. The proposal always contains `defaultBranch`.
- `init_config.py` renames `configPath` and `exists` to `legacyConfig` and `legacyExists`.

### Removed

- `/argani:init` no longer asks for `artifactRoot` (a board project keeps its jobs in `tasks/`) nor
  for `recordCommitMessage`, and no longer detects commitlint scopes.

## [0.9.0] - 2026-10-28

### Added

- `scripts/argani_config.py` reads the argani config keys from the project's `project.json` in the
  argani home. `load_project_config(home, name)` gives a project's effective config without git.
- The effective config reports `project`, `home` and `tasksDir`; `tasks_dir()` and `job_dir()` give
  the job folders (`<home>/projects/<name>/tasks/<slug>` for a project).
- `project_registry.project_of_path()` tells which project's folder a path in the home is in.

### Changed

- A repository registered as a project ignores its `.claude/argani.json` (with a note on stderr);
  `.claude/argani.json` stays as a fallback for unregistered repositories until 1.0.0.
- A broken home or project registry is ignored with a note, never blocking a repository.
- `artifact_check.py` takes `branchTypes` from the project when the file is in its hub tasks folder.

## [0.8.0] - 2026-10-28

### Added

- The project registry: `projects/<name>/project.json` in the argani home holds a project's identity
  (`name`, `remotes`, `paths`). `scripts/project_registry.py [dir]` reports which project a
  directory belongs to, matching the repository's normalized git remotes first and its real path
  second, so clones and worktrees share a project. A broken entry is skipped with a warning, two
  projects claiming one remote is an error, and the home itself is never a project. Nothing uses
  the registry yet.

## [0.7.0] - 2026-10-28

### Added

- The argani home: `$ARGANI_HOME`, else `~/.argani`, the folder that will hold the board of every
  project. `scripts/argani_home.py` reports it and, with `--create`, makes the missing folders
  (the home and `projects/`) without touching existing files. A relative path or one with `..` is
  refused. Nothing uses the home yet.

## [0.6.1] - 2026-10-28

### Removed

- `bootstrap/` and its tests: it installed one person's global `CLAUDE.md` and is not part of the
  plugin. Install argani with `claude plugin marketplace add` and `claude plugin install` as the
  README describes.

## [0.6.0] - 2026-10-28

### Added

- `commitSkill`: a repository skill through which every argani commit is made. The builder gets
  the Skill tool and commits only through it (and stops with `STOPPED commit skill <name>
  unavailable` if it cannot), and the orchestrator's record commits use it with the job folder as
  the unit. The skill decides staging, scope and trailers, so `commitTrailers` is not added on
  top. Without it, commits work as before. `/argani:init` offers a `.claude/skills/*commit*` skill.
- `agentModels`: the model each argani agent runs on, passed by the skills when they spawn the
  agent (`inherit` leaves it to the session). Only the agents to change need to be given. A value
  may choose by the job's risk (`{"default": ..., "low"|"medium"|"high": ...}`), and a
  `reviewer:<checklist>` key overrides `reviewer` for one checklist.
- Job risk: an optional `Risk: low|medium|high` header line in `intent.md` (default `medium`),
  checked by `artifact_check.py` and asked by `/argani:intent`.
- `reviewerPaths`: path globs per checklist; that reviewer runs only when the job's diff touches one
  of them. `factory_state.py` reports the job's `risk`, its `reviewers`, and the `models` resolved
  for each agent and reviewer seat. The factory and review skills use them, and a round is
  complete without a skipped reviewer.

### Changed

- Default models follow the weight of each task: spec-writer and approver `opus`; builder `sonnet`,
  `opus` when risk is high; reviewers `sonnet`, `haiku` when risk is low, with `security` on `opus`,
  `ux` on `sonnet`, and `ui-design`, `citation` and `format` on `haiku`. It used to be reviewer
  `sonnet` and the others `inherit`. Every agent's frontmatter is now `inherit`.
- `glob_to_regex` moved from the artifact guard to `argani_config.py`, shared with `reviewerPaths`.

## [0.5.0] - 2026-10-28

### Changed

- **The git guard only gates merging.** argani no longer overrides a repository's own git rules.
  Held, as before, for the main session (ask) and now for every subagent alike (deny): a push
  that lands on a protected branch, a `git merge` while on a protected branch, and a PR/MR merge,
  which now also covers a merge through `gh api` / `glab api`. Pushing and pulling job branches,
  and merging into them, follow the repository's rules: the blanket subagent ban on push, pull,
  merge and send-pack (0.2.0) is removed, and so are its false positives, such as
  `grep merge notes.md && git status`. `git pull` is no longer held anywhere. The builder's
  instructions say the same.

### Fixed

- `test_bootstrap.py` skips when `bootstrap/` is absent, as in an installed copy of the plugin,
  instead of failing with FileNotFoundError.

## [0.4.1] - 2026-10-28

### Fixed

- `/argani:init` offers `mrCommand` candidates with `{base}`, which the factory fills since 0.4.0,
  instead of a literal `{baseBranch}` the human had to replace by hand.

## [0.4.0] - 2026-10-27

### Added

- Job types. `branchPattern` may contain `{type}` once, filled from a new `Type:` header line in
  `intent.md`. `branchTypes` lists the allowed types (required with `{type}`), and
  `baseBranchByType` gives a type its own base branch, for example a Git Flow hotfix from `main`;
  those bases are protected too. `artifact_check.py intent` rejects an intent without a listed
  type when `branchTypes` is set. `factory_state.py` reports `type`, and derives `branch` and
  `base_branch` per job. `/argani:review` diffs against the job's base, and `/argani:intent` asks
  for the type.
- `mrCommand` accepts `{base}`, replaced by the job's base branch.
- `/argani:init` offers `{type}/{slug}`, with the existing branch prefixes as `branchTypes`.

### Changed

- The intent template has a `Type:` line; delete it when the repository sets no `branchTypes`.

## [0.3.0] - 2026-10-27

### Changed

- `commitTrailers` accepts a `{model}` placeholder, replaced by the name of the model that makes the
  commit (the main session for record commits, the builder for its own), so a trailer stays right
  when sessions or agents run on different models. It is the only placeholder; any other `{...}`
  makes the config invalid.
- **Default change:** `commitTrailers` defaults to `["Co-Authored-By: {model} <noreply@anthropic.com>"]`
  instead of `[]`. Repositories that want no trailer set `"commitTrailers": []`.
- `/argani:init` offers the default trailer as its candidate.

## [0.2.0] - 2026-10-27

First tagged release. Installed copies of the earlier untagged `0.1.0` do not update by
themselves: run `claude plugin marketplace update argani`, then reinstall or update `argani@argani`.

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
- `artifactRoot` is validated: it must be a folder relative to the toplevel, without `..` and not under
  `.git` (an empty, absolute or escaping value made the factory and the artifact guard use paths outside
  the repository). Surrounding slashes and `./` are dropped. `/argani:init` now asks for it.
- **Breaking:** acceptance criteria are a numbered task list, `n. [ ] <claim> — verify: <how>`,
  numbered 1 to n in order; item n is still referred to as AC-n everywhere else. `artifact_check.py`
  rejects the old `- AC-n: ...` bullets with a message showing the new shape, and accepts a ticked
  box. To migrate an intent, rewrite `- AC-n: <claim>` as `n. [ ] <claim>`.
- Acceptance criteria may read `verify: manual: <step>` for checks only a human can do; the step must
  be named (`manual: TBD` fails `artifact_check.py`). The builder lists them under
  `## Pending human verification` in `build.md`, the compliance reviewer checks that list instead of
  evidence, the approver does not escalate because of them and copies them into `decision.md` as
  `## Human verification before merge`, and the factory carries that checklist into `mr.md`.
- Skill `/argani:init` and `scripts/init_config.py`: propose `.claude/argani.json` from the repository
  (test entry point, shared branch prefixes, commitlint scopes resolved by the repository's own
  commitlint, a `develop` branch, the remote host for `mrCommand`), ask what cannot be detected,
  write and validate the file. It never overwrites an existing config and never commits.
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
