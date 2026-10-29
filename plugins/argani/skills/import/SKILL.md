---
name: import
description: Move the legacy job folders of this project (argani/<slug> in the working tree) to the project's task folder in the argani home. Copies and verifies; never writes into the project and never deletes. Slash form /argani:import [<slug> ...].
argument-hint: "[<slug> ...]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read
---

# /argani:import

Before 1.0.0 a project kept its jobs at `<artifactRoot>/<slug>/` (default `argani/<slug>`). This
skill copies them to `projects/<name>/tasks/<slug>/` in the argani home. Only the working tree is
read: a job that lives only on a branch must be checked out first, with the project's own tools.
The project is never modified and nothing is deleted.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If `project` is null, say the
   directory is not registered, tell the human to run `/argani:init` first, and stop.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/import_jobs.py` (a dry run), adding
   `--slug <slug>` for each argument the human gave. Never pass anything else the human typed. Show
   the plan: per job the `files`, the `skipped` entries (symbolic links are never copied), and the
   `status`: `new`, `already-imported`, `conflict`, `missing` or `failed`. Show `artifactRoot` and
   its `artifactRootSource`; if the folders are elsewhere, rerun with `--artifact-root <folder>`.
   If `jobs` is empty, say there are no legacy jobs in the working tree to import (a job that lives
   only on a branch has to be checked out first) and stop.
3. Ask the human to confirm the list. A conflict means the destination folder holds different or
   extra files: it is not written; the human resolves it by hand (delete or rename the
   destination), then runs the skill again. `already-imported` needs nothing.
4. Run the same command with `--apply` and the same `--slug` arguments. If it exits non-zero, show
   its output (a copy that fails verification is removed again; earlier imports of the run stay,
   and the message names them). Otherwise show the `stage_after` per job and suggest `/argani:board`.
5. Tell the human that the project is untouched: the old folders (`<artifactRoot>/<slug>`) and
   `.claude/argani.json` can now be removed through the project's own process, and that
   `.claude/argani.json` is no longer read since 1.0.0. This skill writes nothing into the project
   and never deletes.
