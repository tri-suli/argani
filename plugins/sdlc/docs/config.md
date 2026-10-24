# Configuration: `.claude/sdlc.json`

Per-repository settings for the `sdlc` plugin. The file is optional; every key has a default.

## Location

The file is `<repository toplevel>/.claude/sdlc.json`. The toplevel is found with
`git -C <current working directory> rev-parse --show-toplevel`, **not** from `CLAUDE_PROJECT_DIR`,
so the right file is used in worktrees and inside subagents. Scripts and hooks must resolve it
through `scripts/sdlc_config.py`. Outside a git repository the defaults apply and `toplevel` is `null`.

## Keys

| Key | Default | Meaning |
|---|---|---|
| `artifactRoot` | `"sdlc"` | Folder (relative to the toplevel) holding `<slug>/` artifact folders. |
| `defaultBranch` | detected | Branch that agents must never push or merge to. Detected from `git symbolic-ref refs/remotes/origin/HEAD` (leading `origin/` removed), else `"main"`. |
| `verifyCommand` | none | Command that proves the work (tests, linters, link check). Required by factory mode. |
| `reviewers` | `["code"]` | Names of checklists from the catalog that reviewers apply. |
| `protectedPaths` | `[]` | Globs relative to the toplevel that agents must not write. |
| `mrCommand` | none | Command that opens the merge request; `{branch}` is replaced by the working branch. Without it, nothing is pushed. |

## Example

```json
{
  "artifactRoot": "sdlc",
  "defaultBranch": "main",
  "verifyCommand": "npm test",
  "reviewers": ["code", "security", "compliance"],
  "protectedPaths": ["raw/**", "archive/**"],
  "mrCommand": "gh pr create --fill --base main --head {branch}"
}
```

## Reading the effective config

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py [dir]
```

Prints the merged configuration as JSON, plus `toplevel`.
