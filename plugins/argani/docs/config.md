# Configuration: `project.json` in the argani home

Settings for the `argani` plugin. They live in the project's `project.json` in the [argani
home](#argani-home), beside its identity keys (`name`, `paths`); the keys are the ones documented
below. A directory that is not registered as a project gets the defaults, and `tasksDir` is `null`.
The old per-repository `.claude/argani.json` is no longer read (since 1.0.0). A broken home or
project registry never blocks a project: it is ignored with a note on stderr, even in strict mode.

argani never runs git and has no setting about branches, worktrees, commits or merges: those belong
to the project and its own tools. Keys of argani 1.x that were about them (`defaultBranch`,
`baseBranch`, `protectedBranches`, `branchPattern`, `branchTypes`, `baseBranchByType`,
`branchNumberCommand`, `worktreePath`, `worktreeCommand`, `mergePolicy`, `mergeCommand`,
`commitTrailers`, `commitSkill`) are ignored when they are still in a `project.json`; scripts print
a note on stderr naming them.

Every key is optional and has a default, except that factory mode and the review need
`verifyCommand` and `diffCommand`. `/argani:init` proposes the config from what the directory
already uses (test command), asks for the rest, validates it and registers the project; it carries
over the keys of an old `.claude/argani.json` and never overwrites an existing project.

## Location

The file is `<home>/projects/<name>/project.json`. The project of a directory is found from the
real path of the directory (the current working directory of the script, **not**
`CLAUDE_PROJECT_DIR`) and of its ancestors, matched against the `paths` of the registered projects;
the nearest match wins. An entry of `paths` may be a pattern (see "The argani home"), so a checkout
nested inside a registered path can be its own project root. Scripts and hooks must resolve it
through `scripts/argani_config.py`.
Outside every project the defaults apply and `tasksDir` is `null`.

If the project file is unreadable, not valid JSON, or has a wrongly typed key, scripts use the
defaults (with a note on stderr). The artifact guard cannot check `protectedPaths` then, so it asks
(main session) or denies (subagent) for every write inside the project until the file is fixed.

## Keys

| Key              | Default       | Meaning                                                                                                                                                                                                                                                                                                                      |
|------------------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `verifyCommand`  | none          | Command that proves the work (tests, linters, link check), run by the builder in the working directory. Required by factory mode.                                                                                                                                                                                      |
| `diffCommand`    | none          | The project's command that prints the change under review as a unified diff. `capture_change.py` runs it before each review round with the project root (the nearest registered path or pattern match that contains the working directory) as working directory, so the paths in the diff line up with `reviewerPaths` and `protectedPaths`; 120 s limit, 1 MB or more is warned about because reviewers read a large diff partially. It saves the output unchanged as `review/round-<N>/change.diff`. Required by factory mode and the review. See "Choosing `diffCommand`". |
| `reviewers`      | `["code"]`    | Names of checklists from the catalog that reviewers apply.                                                                                                                                                                                                                                                                   |
| `reviewerPaths`  | `{}`          | Path globs per checklist (same syntax as `protectedPaths`), for example `{"security": ["src/auth/**"]}`. A checklist listed here runs only when the captured `change.diff` touches one of its globs; the others always run. Without a `change.diff` (or one that is not a unified diff) every reviewer runs. Keys must be listed in `reviewers`. |
| `protectedPaths` | `[]`          | Globs relative to the project directory that agents must not write.                                                                                                                                                                                                                                                         |
| `mrCommand`      | none          | Command that opens the merge request. `{title}` is the title (the output of `mrTitleCommand` when set, else the intent's heading) and `{bodyFile}` the path of the generated description (acceptance criteria, human checklist, task folder). argani shell-quotes each value, so write the placeholders without quotes (a quoted placeholder is rejected, as is any other placeholder). Without it, the factory only prints the description. |
| `mrTitleCommand` | none          | Command that prints the merge request title, for projects whose titles follow a convention argani cannot derive. `{title}` is the intent's heading and `{slug}` the task slug, shell-quoted by argani like `mrCommand` (write them without quotes). Runs in the working directory with a 30 s timeout; the first non-empty line of stdout is the title. A failure or an empty output stops the merge request step. Examples: `scripts/mr-title.sh {slug}`, `printf '[feat]: %s' {title}`. |
| `agentModels`    | see below     | Model of each argani agent: `sonnet`, `opus`, `haiku`, `fable` or `inherit` (the session's model), or an object choosing by the job's risk, `{"default": ..., "low"\|"medium"\|"high": ...}`. Keys are `spec-writer`, `builder`, `approver`, `reviewer`, and `reviewer:<checklist>`, which wins over `reviewer`. Give only the keys to change; the others keep their default (see "Models" below). |

## Choosing `diffCommand`

The command must match how the builder keeps its work, which is the project's own commit rule:

- `git diff origin/main...HEAD` shows **committed work only**. Use it when the builder commits.
- `git diff origin/main` shows the working tree against the base, but **not untracked files**. Use it
  when the project forbids agent commits; new files need `git add -N <path>` (intent to add) to
  appear in it, so have the builder's rules or your own routine do that.

When the project works in checkouts nested inside the registered path (for example worktrees under
`.worktrees/`), list them as a pattern in `paths`; otherwise `diffCommand` runs in the outer checkout
and prints nothing.

A mismatch shows up as an empty capture ("diffCommand printed nothing; nothing to review"), which
stops the factory: check `diffCommand` against the builder's commit rule first. The change of a round
is fixed once a reviewer has worked on it: `capture_change.py` refuses to replace the `change.diff`
of a round that already holds a review (the only exception is a round reviewed before 2.0.0, at
stage `needs-decision`, whose `change.diff` is missing).

## Models

Default `agentModels`, by the weight of each task and the job's `Risk:` (`medium` when the intent
has no `Risk:` line):

| Agent                                   | Model                                     | Why                                                       |
|-----------------------------------------|-------------------------------------------|-----------------------------------------------------------|
| orchestrator, intake (`/argani:intent`) | the session's model                       | interactive with the human, not a subagent                |
| `spec-writer`                           | `opus`                                    | design decisions; a wrong spec costs every later stage    |
| `builder`                               | `sonnet`; `opus` when risk is high        | guided by the spec and checked by the verify command      |
| `reviewer` (`code`, `compliance`, ...)  | `sonnet`; `haiku` when risk is low        | checklist-driven, and the approver checks the round       |
| `reviewer:security`                     | `opus`                                    | a missed vulnerability is expensive                       |
| `reviewer:ux` / `reviewer:ui-design`    | `sonnet` / `haiku`                        | judging flows / checking tokens and components            |
| `reviewer:citation`, `reviewer:format`  | `haiku`                                   | mechanical checks                                         |
| `approver`                              | `opus`                                    | the last gate before the human                            |

Example: a cheaper builder except for risky jobs, and security reviewed only when auth code changes:

```json
{
  "agentModels": { "builder": { "default": "haiku", "high": "opus" } },
  "reviewers": ["code", "security"],
  "reviewerPaths": { "security": ["src/auth/**", "**/*permission*"] }
}
```

## `protectedPaths` glob semantics

Patterns are matched against the file's path relative to the project directory (the registered
path that contains it; forward slashes), anchored at both ends:

- `*` and `?` match within one path segment and never cross `/`.
- `**` matches across segments: `raw/**` covers everything below `raw/`; `docs/**/secret.md`
  matches `docs/secret.md` and `docs/a/b/secret.md`.
- A pattern without `/` is still anchored at the project directory: `*.lock` matches `poetry.lock`,
  not `sub/poetry.lock` (use `**/*.lock`).
- No character classes (`[abc]`) or negation.

A match denies `Write` and `Edit` for everyone, main session included. Writes through `Bash` are not
guarded; the builder has full `Bash` and is told not to touch the task folder except `plan.md` and
`build.md`.

Symlinks: a path is checked where it resolves and, for each symlinked folder on the way, as written
in the project that holds the symlink. So a protected folder stays protected when it is a symlink,
whether it points into another directory of the project or to a folder outside any project. `mv`,
`rm` and other writes through Bash are not covered.

## Example

```json
{
  "verifyCommand": "npm test",
  "diffCommand": "git diff origin/main...HEAD",
  "reviewers": ["code", "security", "compliance"],
  "protectedPaths": ["raw/**", "archive/**"],
  "mrTitleCommand": "scripts/mr-title.sh {slug}",
  "mrCommand": "gh pr create --title {title} --body-file {bodyFile}"
}
```

## Reading the effective config

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py [dir]
```

Prints the merged configuration as JSON, plus the `project` name (`null` for a directory without a
project), the `home`, `projectRoot` (the nearest registered path or pattern match that contains `dir`) and `tasksDir`, the
folder of the job folders: `<home>/projects/<name>/tasks` for a project, `null` without one. The
identity keys are never part of it. `null` values are ignored and types are checked (`reviewers` and
`protectedPaths` must be lists of strings, the other keys strings). An unusable file makes the
command exit 1 with an error on stderr, while `load_config()` falls back to the defaults with a note
on stderr so that hooks fail open.

## argani home

The board that holds every project's tasks lives in the argani home: `$ARGANI_HOME` when set, else
`~/.argani`. It is a folder of the user, apart from the plugin (whose installed copy is replaced on
every release) and from the projects. `ARGANI_HOME` must be an absolute path (a leading `~` is
expanded) without `..`.

`python3 <plugin root>/scripts/argani_home.py` prints the home and whether its folders exist;
`--create` makes the missing folders only (the home and `projects/`) and never touches existing
files. Its parent folder must already exist. The home is a plain folder; what the user does with it
(backup, sync, version control) is theirs, and argani writes nothing of its own beyond the files
described here. If the home is under version control, add `board.md` to its ignore list: the board
is regenerated.

`/argani:init` registers a directory as a project: it detects the settings, asks what cannot be
detected, and runs `python3 <plugin root>/scripts/register_project.py <name> <dir> < config.json`,
which creates the home when missing and writes `projects/<name>/project.json` (identity keys plus
the config keys read from stdin, validated like any config). The directory may be any directory; its
real path is registered and no git is needed. Registering the same project from another directory
only appends that path. The script never writes into the directory. `tasksDir` in the output of
`argani_config.py` is where the skills write the artifacts.

Each project registered on the board has an entry, `projects/<name>/project.json`:

```
<home>/
  projects/
    <name>/project.json     {"name": "<name>", "paths": [...]}
    <name>/tasks/<slug>/    intent.md, spec.md, plan.md, build.md, review/, decision.md, mr.md
```

`name` matches `[a-z0-9][a-z0-9-]*` and equals the folder name. `paths` are the real paths of the
project's directories. An entry may also be a pattern: `*` and `?` stay inside one path segment; there is no `**`
(it is two `*`, so `.worktrees/**` is `.worktrees/*`). Patterns are added by hand to
`project.json` (`register_project.py` registers real directories only), for example
`"paths": ["/p/app", "/p/app/.worktrees/*"]`: inside `/p/app/.worktrees/job-a/src` the project root is
`/p/app/.worktrees/job-a`, inside `/p/app/src` it is `/p/app`, and the pattern never matches
`/p/app` or `/p/app/.worktrees` themselves. A directory belongs to the project that lists its real
path or matches it by a pattern, or does so for its nearest ancestor that any project lists; a path
matched by two projects is an error. That nearest ancestor is the project root used by
`diffCommand`, `protectedPaths` and `reviewerPaths`. The home itself is never a project. A broken
entry is skipped with a warning on stderr so it cannot block other projects. A leftover `remotes`
key from argani 1.x is ignored.
`python3 <plugin root>/scripts/project_registry.py [dir]` prints the project of `dir` (default: the
current directory) and exits 1 when there is none.
