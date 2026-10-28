---
name: init
description: Create .claude/argani.json for this repository from what it already uses (test command, branch prefixes, commitlint scopes, remote host), asking only what cannot be detected. Use when a repository has no argani config yet, or when the factory stops because verifyCommand is missing. Slash form /argani:init.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Write
---

# /argani:init

Keys and their meaning: `${CLAUDE_PLUGIN_ROOT}/docs/config.md`. This skill writes one file,
`<toplevel>/.claude/argani.json`, and never commits it.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_config.py`. If it exits non-zero, show its output
   and stop. Keep the JSON.
2. If `exists` is true, **stop**: show the current file and say to edit it by hand (keys in
   `docs/config.md`). Never overwrite it.
3. Show `proposal` as the starting point. Then ask the human about each entry in `questions`, a few
   at a time, offering its `candidates` (none means an open question). Rules for the answers:
   - `artifactRoot`: the folder for job folders, relative to the toplevel (for example
     `docs/tasks`); no absolute path, no `..`, not under `.git`. Omit it to keep `argani`.
   - `verifyCommand`: required; the factory refuses to run without it. A command that fails until
     the first job adds tests is fine.
   - `branchPattern`: must contain `{slug}` exactly once; keep the default `feature/{slug}` unless
     the human picks another. With `{type}` (one prefix per kind of job), also set `branchTypes`
     (start from the question's `types`) and, for types that start from another branch (a hotfix
     from `main` in Git Flow), `baseBranchByType`; `mrCommand` can then use `{base}`.
   - `baseBranch`: set it only when jobs should not branch from `defaultBranch`.
   - `recordCommitMessage`: `<type>(<scope>): record {slug} {what}` with a type and scope the
     repository's commit rules accept; `{what}` exactly once.
   - `commitTrailers`: trailer lines; `{model}` becomes the committing agent's model name. Omit the
     key to keep the default `Co-Authored-By: {model} <noreply@anthropic.com>`; `[]` for none.
   - `mrCommand`: optional; keep `{branch}` and `{base}` as they are, the factory fills them with the
     job branch and its base branch. Leave it out when the human wants to push and open merge
     requests themselves.
   Ask also whether to add checklists to `reviewers` (catalog in `docs/config.md`) and whether some
   paths must never be written by agents (`protectedPaths`). Omit keys the human leaves at their
   default.
4. Show the final JSON and ask for confirmation. On yes, write it to `configPath` (two-space
   indent, trailing newline). Claude Code asks the human before writing under `.claude/`; if the
   write is refused, never write it another way (no Bash): give the human the JSON and the
   validation command of step 5, and stop.
5. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If it exits non-zero, show the error,
   fix the file with the human, and run it again.
6. Tell the human the file is not committed. It belongs on the base branch before the first job:
   commit it there through the repository's usual process, so job branches and worktrees created
   from the base branch already have it. Next step: `/argani:intent <description>`.
