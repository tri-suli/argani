---
name: spec
description: Write or approve a spec.md from an approved intent, the second artifact of the argani loop. Use when an intent is approved and needs a design, or when a spec needs approval. Slash form /argani:spec <slug> or /argani:spec approve <slug>.
argument-hint: "<slug> | approve <slug>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git config user.name), Bash(date +%F), Read, Write, Edit, Glob, Grep
---

# /argani:spec

Background on the loop, statuses and rules: `${CLAUDE_PLUGIN_ROOT}/docs/argani.md`.
This skill never writes code.

## Setup

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If it fails, show its error and stop.
   Read `tasksDir` and `project` from the JSON. Then:
   - `tasksDir` set: `<artifact dir>` is `tasksDir`, the folder that holds the job folders; a job
     folder is `<artifact dir>/<slug>/`. It is the task folder of the project in the argani home: the
     job folder is outside the repository and nothing is written into it.
   - `tasksDir` null (not in a git repository, or the repository is not registered): stop. argani
     works from inside a registered project repository; say to open the repository and run
     `/argani:init` if it is not registered yet.
   Always pass the full path under `<artifact dir>` to `artifact_check.py`: it reads `branchTypes`
   from the file's location.
2. Artifact language: the language of this repository's CLAUDE.md, else the user's. Only the
   prose is in that language. The `# Spec:` title prefix, the `##` section headings, file names,
   `Status:` lines, `AC-n`, `verify:` and verdict words always stay English.
3. Mode: it is `approve` only when `$ARGUMENTS` is exactly two tokens, `approve <slug>`, and the
   folder `<artifact dir>/<slug>/` exists. Otherwise `$ARGUMENTS` is the `<slug>`.

## Write mode

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py status <artifact dir>/<slug>/intent.md`.
   - Non-zero exit: stop and show the violations.
   - Prints `draft`: **stop**. Name the file, say the intent is not approved, and tell the user to
     run `/argani:intent approve <slug>`. Do not write spec.md.
2. If `spec.md` already exists in that folder, stop and ask before touching it.
3. Read the repository's CLAUDE.md and the code or documents the intent touches.
4. Write `spec.md` from `${CLAUDE_PLUGIN_ROOT}/templates/spec.md` with `Status: draft`:
   - Approach, and rejected alternatives.
   - Affected areas, as concrete paths.
   - Acceptance criteria mapping: one row per AC from the intent, with a concrete way to verify it.
   - Flagged concerns: especially policies or constraints that conflict with each other or with
     the approach. Never resolve a conflict silently; flag it.
   - Open questions carried forward from the intent, plus new ones.
5. Run `artifact_check.py spec <file>`; fix until `VALID`.
6. Remind the user that the human reviews the spec and does not write it: correct it by comment
   or edit, then run `/argani:spec approve <slug>`.

## Approve mode

1. Run `artifact_check.py status <artifact dir>/<slug>/spec.md`.
   - Non-zero exit: refuse, show the violations verbatim, never set the approved status.
   - Prints `approved`: say it is already approved and stop.
2. Run `git config user.name`. If it is empty, stop and ask the user to set it.
3. Run `date +%F`, then replace the Status line with
   `Status: approved by <user.name> on <YYYY-MM-DD>`.
4. Run `artifact_check.py status` again; it must print `approved`. If not, restore `Status: draft`
   and show the violations.
5. Say what comes next: `/argani:plan <slug>`.
