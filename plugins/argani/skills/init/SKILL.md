---
name: init
description: Register this repository as a project on the argani board (in the argani home, ~/.argani by default) from what it already uses (test command, branch prefixes, remote host), asking only what cannot be detected. Never writes into the repository. Use when a repository is not registered yet, or when the factory stops because verifyCommand is missing. Slash form /argani:init.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read
---

# /argani:init

Keys and their meaning: `${CLAUDE_PLUGIN_ROOT}/docs/config.md`. This skill writes one file,
`projects/<name>/project.json` in the argani home, through `register_project.py`. It never writes
into the repository.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_config.py`. If it exits non-zero, show its output
   and stop. Keep the JSON.
2. If `homeError` is set, explain it (`ARGANI_HOME` must be an absolute path without `..`) and stop.
   If `registryError` is set, the registry in the home is inconsistent (for example two projects
   claim one remote): show the message, tell the human to fix the entries under `projects/` by
   hand, and stop.
3. If `registered` is set, say the repository already belongs to the project `registered`, show
   `projectFile`, and tell the human to edit that file by hand to change keys such as
   `verifyCommand` (keys in `docs/config.md`), then run
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py` to validate it. Then stop.
4. Show `proposal` as the starting point, with the project name (`project`) and the file that will
   be written (`projectFile`). Then ask the human about each entry in `questions`, a few at a time,
   offering its `candidates` (none means an open question). Rules for the answers:
   - `project`: asked when the repository has no remote, or when `nameTaken` is true (the name
     belongs to another repository, so pick another); lowercase letters, digits and dashes,
     starting with a letter or digit. It becomes the folder `projects/<name>` in the home.
   - `verifyCommand`: required; the factory refuses to run without it. A command that fails until
     the first job adds tests is fine.
   - `branchPattern`: must contain `{slug}` exactly once; keep the default `feature/{slug}` unless
     the human picks another. With `{type}` (one prefix per kind of job), also set `branchTypes`
     (start from the question's `types`) and, for types that start from another branch (a hotfix
     from `main` in Git Flow), `baseBranchByType`; `mrCommand` can then use `{base}`. `{n}` (at most
     once) puts a running job number in the branch name, like `feat/common-{n}-{slug}`; candidates
     with it come from existing branches such as `feat/common-56-x`.
   - `branchNumberCommand`: asked only when the pattern has `{n}`; a one-line shell command, run in
     the repository, that prints the next job number. Omit it to let argani count from the existing
     intents. Ask it also when the human types a pattern with `{n}` themselves.
   - `defaultBranch`: asked when git cannot tell it; the board reads it without a checkout.
   - `commitTrailers`: trailer lines; `{model}` becomes the committing agent's model name. Omit the
     key to keep the default `Co-Authored-By: {model} <noreply@anthropic.com>`; `[]` for none.
   - `commitSkill`: the repository skill every argani commit must go through (the builder and the
     record commits use it instead of `git commit`; it then decides trailers). Omit it to commit
     with `git commit` and `commitTrailers`.
   - `baseBranch`: set it only when jobs should not branch from `defaultBranch`.
   - `mrCommand`: optional; keep `{branch}` and `{base}` as they are, the factory fills them with the
     job branch and its base branch. Leave it out when the human wants to push and open merge
     requests themselves.
   - `mergePolicy`: `human` (default, omit the key) keeps merging a human step; `agent` lets the factory
     merge the merge request after APPROVE and then needs `mergeCommand` (candidates by host; keep `{mr}`
     as it is, the factory fills it with the merge request URL or number from `mr.md`). Ask `mergeCommand`
     only when the human picks `agent`. Branch protection on the remote still applies.
   - `worktreePath`: when asked, jobs run in their own git worktree under that pattern (`{branch}`
     stays as it is) and the factory never switches branches in the main checkout; remind the human to
     add the folder to `.gitignore`. `worktreeCommand` is optional (see `docs/config.md`).
   Ask also whether to add checklists to `reviewers` (catalog in `docs/config.md`) and whether some
   paths must never be written by agents (`protectedPaths`). Omit keys the human leaves at their
   default, but keep `defaultBranch` from the proposal.
5. If `legacyExists` is true, explain that the repository's `.claude/argani.json` is ignored once
   the project is registered, and that its keys (`legacyKeys`) are already part of the proposal and
   win over the detected values. Only `artifactRoot` is not carried over: a board project keeps its
   jobs in `tasks/`. Keys listed in `legacyUnknownKeys` are not argani keys and are left behind. If `legacyKeys` is null, show `legacyError` and continue without them. Suggest
   removing the file from the repository later, through its usual process; never delete it.
6. Show the final config JSON and the project name, and ask for confirmation. On yes, run it with
   the config on stdin:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/register_project.py <name> <toplevel> <<'EOF'
   { ...config keys... }
   EOF
   ```

   If it exits non-zero, show the message, fix the config with the human, and run it again. If it
   fails twice in a row, stop and show the message.
7. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py` in the repository and show `project`
   and `tasksDir`. If it exits non-zero, show the error, tell the human to fix `projectFile` by
   hand, and stop.
8. End with: nothing was written into the repository. Next step: `/argani:intent <description>`.
