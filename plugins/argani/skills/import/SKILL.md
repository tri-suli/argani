---
name: import
description: Move the legacy job folders of this repository (argani/<slug>, on the working tree and on its branches) to the project's task folder in the argani home. Copies and verifies; never writes into the repository and never deletes. Slash form /argani:import [<slug> ...].
argument-hint: "[<slug> ...]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read
---

# /argani:import

Before the board a repository kept its jobs at `<artifactRoot>/<slug>/` (default `argani/<slug>`),
committed on the job branches. This skill copies them to `projects/<name>/tasks/<slug>/` in the
argani home. The repository is never modified and nothing is deleted.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If `project` is null, say the
   repository is not registered, tell the human to run `/argani:init` first, and stop.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/import_jobs.py` (a dry run), adding
   `--slug <slug>` for each argument the human gave. Never pass anything else the human typed. Show
   the plan: per job the `source` (`worktree` or a branch), the `candidates` when there is more
   than one (with `differs` and the `reason` for the choice) so the human sees the ambiguity, the
   `files`, the `skipped` entries (symbolic links and submodules are never copied), and the
   `status`: `new`, `already-imported`, `conflict`, `missing` or `failed`. Show `artifactRoot` and
   its `artifactRootSource`; if the folders are elsewhere, rerun with `--artifact-root <folder>`.
   If `jobs` is empty, say there are no legacy jobs to import and stop.
3. Ask the human to confirm the list. A conflict means the destination folder holds different or
   extra files: it is not written; the human resolves it by hand (delete or rename the
   destination), then runs the skill again. `already-imported` needs nothing.
4. Run the same command with `--apply` and the same `--slug` arguments. If it exits non-zero, show
   its output (a copy that fails verification is removed again; earlier imports of the run stay,
   and the message names them). Otherwise show the `stage_after` per job and suggest `/argani:board`.
5. Say whether the import was recorded: `recorded` is true when the home is a git repository of its
   own, in which case the script committed the imported jobs there; otherwise they stay as files.
6. Tell the human that the repository is untouched: the old folders (`<artifactRoot>/<slug>` on
   their branches) and `.claude/argani.json` can now be removed through the repository's normal
   process (a branch, a commit, a merge request), and that 1.0.0 drops the legacy fallback. This
   skill writes nothing into the repository and never deletes.
