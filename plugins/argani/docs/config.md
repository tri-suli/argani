# Configuration: `project.json` in the argani home

Settings for the `argani` plugin. They live in the project's `project.json` in the [argani
home](#argani-home), beside its identity keys (`name`, `remotes`, `paths`); the keys are the ones
documented below. `.claude/argani.json` in the repository still works as a fallback for a
repository that is not registered as a project, and 1.0.0 removes it. When a repository has both,
the project wins and scripts print `argani: <toplevel>/.claude/argani.json is ignored; the project
<name> is configured in <project file>` on stderr. A broken home or project registry never blocks
a repository: it is ignored with a note on stderr, even in strict mode.

The rest of this page says `.claude/argani.json` where it applies to either file. The file is
optional; every key has a default, except that factory mode needs `verifyCommand`. `/argani:init` proposes the file from what the
repository already uses (test command, branch prefixes, commitlint scopes, remote host), asks for
the rest, writes it and validates it; it never overwrites an existing file and never commits.

## Location

The file is `<repository toplevel>/.claude/argani.json`. The toplevel is found with
`git -C <current working directory> rev-parse --show-toplevel`, **not** from `CLAUDE_PROJECT_DIR`,
so the right file is used in worktrees and inside subagents. Scripts and hooks must resolve it
through `scripts/argani_config.py`. Outside a git repository the defaults apply and `toplevel` is `null`.

If the file is unreadable, not valid JSON, or has a wrongly typed key, scripts and the git guard use
the defaults (with a note on stderr) and keep checking: the default-branch guard still works. The
artifact guard cannot check `protectedPaths` or a custom `artifactRoot` then, so it asks (main
session) or denies (subagent) for every write inside the repository until the file is fixed.

## Keys

| Key                   | Default                                               | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                           |
|-----------------------|-------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `artifactRoot` ¹ | `"argani"`                                            | Folder (relative to the toplevel) holding the `<slug>/` job folders, for example `"docs/tasks"`. Must be relative, must not contain `..` and must not be under `.git`; surrounding slashes and `./` are dropped.                                                                                                                                                                                                                  |
| `defaultBranch`       | detected                                              | The repository's main branch; always protected. Detected from `git symbolic-ref refs/remotes/origin/HEAD` (leading `origin/` removed), else a local `main`, else a local `master`, else `git config init.defaultBranch`, else `"main"`. A repository with both `main` and `master` and no `origin/HEAD` needs an explicit `defaultBranch`.                                                                                        |
| `baseBranch`          | `defaultBranch`                                       | Branch the job branch is created from, the target of the merge request, and the base of every review diff (`<baseBranch>...HEAD`). Always protected.                                                                                                                                                                                                                                                                              |
| `protectedBranches`   | `[]`                                                  | Further branches the git guard protects: pushing to them, merging into them and PR/MR merges are asked in the main session and denied for subagents; everything else follows the repository's own rules. Entries may be globs (`"release/*"`, matched with `fnmatch`, where `*` also matches `/`). The effective list always includes `defaultBranch` and `baseBranch`, so a repository can only add protection, never remove it. |
| `verifyCommand`       | none                                                  | Command that proves the work (tests, linters, link check). Required by factory mode.                                                                                                                                                                                                                                                                                                                                              |
| `reviewers`           | `["code"]`                                            | Names of checklists from the catalog that reviewers apply.                                                                                                                                                                                                                                                                                                                                                                        |
| `protectedPaths`      | `[]`                                                  | Globs relative to the toplevel that agents must not write.                                                                                                                                                                                                                                                                                                                                                                        |
| `mrCommand`           | none                                                  | Command that opens the merge request. `{branch}` is the job branch, `{base}` its base branch (see `baseBranchByType`), `{title}` the title and `{bodyFile}` the path of the generated description (acceptance criteria, human checklist, task folder). argani shell-quotes each value, so write the placeholders without quotes (a quoted placeholder is rejected, as is any other placeholder). Without it, nothing is pushed.                                                                                                                                                                                                                                                           |
| `branchPattern`       | `"feature/{slug}"`                                    | Name of the job branch; `{slug}` is replaced by the job's slug and must appear exactly once. The result must be a valid git branch name and must not be a protected branch. Set the prefix or structure your repository uses, for example `"feat/{slug}"` or `"{slug}"`. It may also contain `{type}` once, filled from the intent's `Type:` line; that needs `branchTypes`.                                                      |
| `recordCommitMessage` | `"chore(argani): record {slug} {what}"`               | Legacy only¹: subject of the commits the factory orchestrator makes to record the job folder in the repository. `{what}` must appear exactly once and becomes `artifacts before build`, `round <N> reviews`, `decision` or `merge request`; `{slug}` is optional. Set it to a type and scope your commit rules accept, for example `"chore(repo): record {slug} {what}"`.                                                                                         |
| `commitTrailers`   | `["Co-Authored-By: {model} <noreply@anthropic.com>"]` | Git trailers added to the builder's code commits and to legacy record commits in the repository; record commits in the argani home carry none. `{model}` is replaced by the name of the model that makes the commit (for example `Claude Sonnet 5.5`), so the trailer stays right when sessions or agents use different models; it is the only placeholder. Each entry must look like `Key: value`. `[]` means no trailer at all.                                                                      |
| `branchTypes`         | `[]`                                                  | Job types an intent may name in its `Type:` header line, for example `["feature", "bugfix", "hotfix"]`. Required when `branchPattern` contains `{type}`; when set, every intent needs a `Type:` from this list. Letters, digits, `.`, `_` and `-` only.                                                                                                                                                                           |
| `baseBranchByType`    | `{}`                                                  | Base branch per job type, for types that do not start from `baseBranch`, for example `{"hotfix": "main"}`. Keys must be listed in `branchTypes`; every value is protected like `baseBranch`.                                                                                                                                                                                                                                      |
| `commitSkill`         | none                                                  | A repository skill (for example `"git-commit"`) through which every argani commit is made: the builder's commits and the orchestrator's record commits use it instead of `git commit`, and it decides staging, scope and trailers, so `commitTrailers` is not added on top. Without it, argani commits with `git commit`.                                                                                                         |
| `agentModels`         | see below                                             | Model of each argani agent: `sonnet`, `opus`, `haiku`, `fable` or `inherit` (the session's model), or an object choosing by the job's risk, `{"default": ..., "low"|"medium"|"high": ...}`. Keys are `spec-writer`, `builder`, `approver`, `reviewer`, and `reviewer:<checklist>`, which wins over `reviewer`. Give only the keys to change; the others keep their default (see "Models" below).                                  |
| `reviewerPaths`       | `{}`                                                  | Path globs per checklist (same syntax as `protectedPaths`), for example `{"security": ["src/auth/**"]}`. A checklist listed here runs only when the job's diff touches one of its globs; the others always run. Keys must be listed in `reviewers`.                                                                                                                                                                               |

¹ Legacy only: `artifactRoot` and `recordCommitMessage` apply to the per-repository `.claude/argani.json`. A project registered in the argani home keeps its jobs in `tasks/` and the factory records them in the home's git repository with a fixed message, so `register_project.py` refuses both keys and `/argani:init` does not carry them over.

Branch names in `defaultBranch`, `baseBranch` and `protectedBranches` are trimmed and lose a
`refs/heads/` prefix. A name that git rejects, a glob outside `protectedBranches`, or a name that
starts with a remote (`origin/develop`) makes the config invalid. An invalid config holds every push,
merge and pull in the git guard.

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

Patterns are matched against the file's path relative to the toplevel (forward slashes), anchored
at both ends:

- `*` and `?` match within one path segment and never cross `/`.
- `**` matches across segments: `raw/**` covers everything below `raw/`; `docs/**/secret.md`
  matches `docs/secret.md` and `docs/a/b/secret.md`.
- A pattern without `/` is still anchored at the toplevel: `*.lock` matches `poetry.lock`, not
  `sub/poetry.lock` (use `**/*.lock`).
- No character classes (`[abc]`) or negation.

A match denies `Write` and `Edit` for everyone, main session included.

Symlinks: a path is checked where it resolves (the repository that holds the target) and, for each
symlinked folder on the way, as written in the repository that holds the symlink. So a protected
folder stays protected when it is a symlink, whether it points into another checkout (as in a
worktree) or to a folder outside any repository. `mv`, `rm` and other writes through Bash are not
covered.

## Example

```json
{
  "artifactRoot": "argani",
  "defaultBranch": "main",
  "verifyCommand": "npm test",
  "reviewers": ["code", "security", "compliance"],
  "protectedPaths": ["raw/**", "archive/**"],
  "mrCommand": "gh pr create --base main --head {branch} --title {title} --body-file {bodyFile}",
  "branchPattern": "feature/{slug}",
  "recordCommitMessage": "chore(argani): record {slug} {what}",
  "commitTrailers": ["Co-Authored-By: {model} <noreply@anthropic.com>"]
}
```

## Branching models

Trunk-based development needs no branch settings: jobs branch from the default branch and merge back
into it.

Git Flow: features branch from `develop` and merge into `develop`, while `main` stays protected:

```json
{
  "defaultBranch": "main",
  "baseBranch": "develop",
  "branchPattern": "feature/{slug}",
  "mrCommand": "gh pr create --base develop --head {branch} --title {title} --body-file {bodyFile}"
}
```

The effective `protectedBranches` is then `["main", "develop"]`.

Job types: several kinds of branch (`feature`, `bugfix`, `hotfix`, ...) need `{type}` in the pattern.
Each intent then states its type in a `Type:` header line, chosen from `branchTypes`, and a type
that starts somewhere else names its base in `baseBranchByType`:

```json
{
  "defaultBranch": "main",
  "baseBranch": "develop",
  "branchPattern": "{type}/{slug}",
  "branchTypes": ["feature", "bugfix", "hotfix"],
  "baseBranchByType": { "hotfix": "main" },
  "mrCommand": "gh pr create --base {base} --head {branch} --title {title} --body-file {bodyFile}"
}
```

An intent with `Type: hotfix` and slug `crash` gets branch `hotfix/crash`, created from `main` and
merged back into `main`; `Type: feature` gets `feature/<slug>` from `develop`. `artifact_check.py`
rejects an intent without a listed type. Every `baseBranchByType` branch is protected as well.
Release branches, which bundle several jobs, are not modelled; cut them by hand.

## Reading the effective config

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py [dir]
```

Prints the merged configuration as JSON, plus `toplevel` and `currentBranch`, the `project` name
(`null` for a legacy repository), the `home`, and `tasksDir`, the folder of the job folders:
`<home>/projects/<name>/tasks` for a project, `<toplevel>/<artifactRoot>` for a legacy repository,
`null` outside git. The identity keys are never part of it. `load_project_config()` reads a project
without git, so it cannot reject remote-prefixed branch names such as `origin/develop`; write plain
branch names. `null` values are
ignored and types are checked (`reviewers` and `protectedPaths` must be lists of strings, the other
keys strings). An unusable file makes the command exit 1 with an error on stderr, while
`load_config()` falls back to the defaults with a note on stderr so that hooks fail open.

## argani home

The board that will hold every project's tasks lives in the argani home: `$ARGANI_HOME` when set,
else `~/.argani`. It is a folder of the user, apart from the plugin (whose installed copy is
replaced on every release) and from the project repositories. `ARGANI_HOME` must be an absolute
path (a leading `~` is expanded) without `..`.

`python3 <plugin root>/scripts/argani_home.py` prints the home and whether its folders exist;
`--create` makes the missing folders only (the home and `projects/`) and never touches existing files.
Its parent folder must already exist. The home is a plain folder: argani never runs `git init` there.
Version control is optional and the user's own choice; when the user makes the home a git repository
of its own (`git init` in the home), the factory records every job folder of a registered project
there (`argani: record <project>/<slug> <what>`; nothing is pushed). Without it the artifacts stay as
files and nothing is committed. The `git` field of the script's output only reports whether the home
is a repository of its own. In a versioned home, add `board.md` to its `.gitignore`: the board is
regenerated and never recorded.

`/argani:init` registers the current repository as a project: it detects the settings, asks what
cannot be detected, and runs `python3 <plugin root>/scripts/register_project.py <name> < config.json`,
which creates the home when missing and writes `projects/<name>/project.json` (identity keys plus
the config keys read from stdin, validated like any config). Registering a second clone of the same
repository only adds its path. The script never writes into the repository. `tasksDir` in the output of `argani_config.py` is where the skills write the artifacts.

Each project registered on the board has an entry, `projects/<name>/project.json`:

```
<home>/
  projects/
    <name>/project.json     {"name": "<name>", "remotes": [...], "paths": [...]}
```

`name` matches `[a-z0-9][a-z0-9-]*` and equals the folder name. `remotes` are normalized git remote
URLs (lowercase host and path, no scheme, user, port or `.git`, so `git@github.com:Org/repo.git` and
`https://github.com/org/repo` are the same; local path remotes keep their case, and relative remotes
are ignored); `paths` are real paths of checkouts that have no shared
remote. A repository belongs to the project that lists any of its remotes, else the project that
lists the real path of its top-level folder; clones and worktrees of one remote therefore share a
project, and two projects claiming one remote is an error. The home itself is never a project. A
broken entry is skipped with a warning on stderr so it cannot block other repositories.
`python3 <plugin root>/scripts/project_registry.py [dir]` prints the project of `dir` (default: the
current directory) and exits 1 when there is none. Later releases add the config and tasks here.
