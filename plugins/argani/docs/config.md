# Configuration: `.claude/argani.json`

Per-repository settings for the `argani` plugin. The file is optional; every key has a default,
except that factory mode needs `verifyCommand`. `/argani:init` proposes the file from what the
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
| `artifactRoot`        | `"argani"`                                            | Folder (relative to the toplevel) holding the `<slug>/` job folders, for example `"docs/tasks"`. Must be relative, must not contain `..` and must not be under `.git`; surrounding slashes and `./` are dropped.                                                                                                                                                                                                                  |
| `defaultBranch`       | detected                                              | The repository's main branch; always protected. Detected from `git symbolic-ref refs/remotes/origin/HEAD` (leading `origin/` removed), else a local `main`, else a local `master`, else `git config init.defaultBranch`, else `"main"`. A repository with both `main` and `master` and no `origin/HEAD` needs an explicit `defaultBranch`.                                                                                        |
| `baseBranch`          | `defaultBranch`                                       | Branch the job branch is created from, the target of the merge request, and the base of every review diff (`<baseBranch>...HEAD`). Always protected.                                                                                                                                                                                                                                                                              |
| `protectedBranches`   | `[]`                                                  | Further branches the git guard protects: pushing to them, merging into them and PR/MR merges are asked in the main session and denied for subagents; everything else follows the repository's own rules. Entries may be globs (`"release/*"`, matched with `fnmatch`, where `*` also matches `/`). The effective list always includes `defaultBranch` and `baseBranch`, so a repository can only add protection, never remove it. |
| `verifyCommand`       | none                                                  | Command that proves the work (tests, linters, link check). Required by factory mode.                                                                                                                                                                                                                                                                                                                                              |
| `reviewers`           | `["code"]`                                            | Names of checklists from the catalog that reviewers apply.                                                                                                                                                                                                                                                                                                                                                                        |
| `protectedPaths`      | `[]`                                                  | Globs relative to the toplevel that agents must not write.                                                                                                                                                                                                                                                                                                                                                                        |
| `mrCommand`           | none                                                  | Command that opens the merge request; `{branch}` is replaced by the job branch and `{base}` by its base branch (see `baseBranchByType`). Without it, nothing is pushed.                                                                                                                                                                                                                                                           |
| `branchPattern`       | `"feature/{slug}"`                                    | Name of the job branch; `{slug}` is replaced by the job's slug and must appear exactly once. The result must be a valid git branch name and must not be a protected branch. Set the prefix or structure your repository uses, for example `"feat/{slug}"` or `"{slug}"`. It may also contain `{type}` once, filled from the intent's `Type:` line; that needs `branchTypes`.                                                      |
| `recordCommitMessage` | `"chore(argani): record {slug} {what}"`               | Subject of the commits the factory orchestrator makes to record the job folder. `{what}` must appear exactly once and becomes `artifacts before build`, `round <N> reviews`, `decision` or `merge request`; `{slug}` is optional. Set it to a type and scope your commit rules accept, for example `"chore(repo): record {slug} {what}"`.                                                                                         |
| `commitTrailers`      | `["Co-Authored-By: {model} <noreply@anthropic.com>"]` | Git trailers added to every commit the orchestrator and the builder make. `{model}` is replaced by the name of the model that makes the commit (for example `Claude Sonnet 5.5`), so the trailer stays right when sessions or agents use different models; it is the only placeholder. Each entry must look like `Key: value`. `[]` means no trailer at all.                                                                      |
| `branchTypes`         | `[]`                                                  | Job types an intent may name in its `Type:` header line, for example `["feature", "bugfix", "hotfix"]`. Required when `branchPattern` contains `{type}`; when set, every intent needs a `Type:` from this list. Letters, digits, `.`, `_` and `-` only.                                                                                                                                                                           |
| `baseBranchByType`    | `{}`                                                  | Base branch per job type, for types that do not start from `baseBranch`, for example `{"hotfix": "main"}`. Keys must be listed in `branchTypes`; every value is protected like `baseBranch`.                                                                                                                                                                                                                                      |

Branch names in `defaultBranch`, `baseBranch` and `protectedBranches` are trimmed and lose a
`refs/heads/` prefix. A name that git rejects, a glob outside `protectedBranches`, or a name that
starts with a remote (`origin/develop`) makes the config invalid. An invalid config holds every push,
merge and pull in the git guard.

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
  "mrCommand": "gh pr create --fill --base main --head {branch}",
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
  "mrCommand": "gh pr create --fill --base develop --head {branch}"
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
  "mrCommand": "gh pr create --fill --base {base} --head {branch}"
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

Prints the merged configuration as JSON, plus `toplevel` and `currentBranch`. `null` values are
ignored and types are checked (`reviewers` and `protectedPaths` must be lists of strings, the other
keys strings). An unusable file makes the command exit 1 with an error on stderr, while
`load_config()` falls back to the defaults with a note on stderr so that hooks fail open.
