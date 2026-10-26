# Configuration: `.claude/argani.json`

Per-repository settings for the `argani` plugin. The file is optional; every key has a default.

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

| Key                 | Default            | Meaning                                                                                                                                                                                                                                                                                                                                    |
|---------------------|--------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `artifactRoot`      | `"argani"`         | Folder (relative to the toplevel) holding `<slug>/` artifact folders.                                                                                                                                                                                                                                                                      |
| `defaultBranch`     | detected           | The repository's main branch; always protected. Detected from `git symbolic-ref refs/remotes/origin/HEAD` (leading `origin/` removed), else a local `main`, else a local `master`, else `git config init.defaultBranch`, else `"main"`. A repository with both `main` and `master` and no `origin/HEAD` needs an explicit `defaultBranch`. |
| `baseBranch`        | `defaultBranch`    | Branch the job branch is created from, the target of the merge request, and the base of every review diff (`<baseBranch>...HEAD`). Always protected.                                                                                                                                                                                       |
| `protectedBranches` | `[]`               | Further branches the git guard protects: a push, merge or pull on them is denied for agents and asked in the main session. The effective list always includes `defaultBranch` and `baseBranch`, so a repository can only add protection, never remove it.                                                                                  |
| `verifyCommand`     | none               | Command that proves the work (tests, linters, link check). Required by factory mode.                                                                                                                                                                                                                                                       |
| `reviewers`         | `["code"]`         | Names of checklists from the catalog that reviewers apply.                                                                                                                                                                                                                                                                                 |
| `protectedPaths`    | `[]`               | Globs relative to the toplevel that agents must not write.                                                                                                                                                                                                                                                                                 |
| `mrCommand`         | none               | Command that opens the merge request; `{branch}` is replaced by the working branch. Without it, nothing is pushed.                                                                                                                                                                                                                         |
| `branchPattern`     | `"feature/{slug}"` | Name of the job branch; `{slug}` is replaced by the job's slug and must appear exactly once. The result must be a valid git branch name and must not be a protected branch. Set the prefix or structure your repository uses, for example `"feat/{slug}"` or `"{slug}"`.                                                                   |

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

## Example

```json
{
  "artifactRoot": "argani",
  "defaultBranch": "main",
  "verifyCommand": "npm test",
  "reviewers": ["code", "security", "compliance"],
  "protectedPaths": ["raw/**", "archive/**"],
  "mrCommand": "gh pr create --fill --base main --head {branch}",
  "branchPattern": "feature/{slug}"
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

The effective `protectedBranches` is then `["main", "develop"]`. Hotfix and release branches, which
start from other bases, are not modelled; run those by hand.

## Reading the effective config

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py [dir]
```

Prints the merged configuration as JSON, plus `toplevel` and `currentBranch`. `null` values are
ignored and types are checked (`reviewers` and `protectedPaths` must be lists of strings, the other
keys strings). An unusable file makes the command exit 1 with an error on stderr, while
`load_config()` falls back to the defaults with a note on stderr so that hooks fail open.
