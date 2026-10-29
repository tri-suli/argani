---
name: intent
description: Write or approve an intent.md, the first artifact of the argani loop. Use when the user wants to start a new piece of work, describe a problem or goal, or approve an intent. Slash form /argani:intent <description> or /argani:intent approve <slug>.
argument-hint: "<description> | approve <slug>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(date +%F), Read, Write, Edit, Glob
---

# /argani:intent

Background on the loop, statuses and rules: `${CLAUDE_PLUGIN_ROOT}/docs/argani.md`.
This skill never writes code.

## Setup

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If it fails, show its error and stop.
   Read `tasksDir` and `project` from the JSON. Then:
   - `tasksDir` set: `<artifact dir>` is `tasksDir`, the folder that holds the job folders; a job
     folder is `<artifact dir>/<slug>/`. It is the task folder of the project in the argani home: the
     job folder is outside the project directory and nothing is written into it.
   - `tasksDir` null (the directory is not registered): stop. argani works from inside a registered
     project directory; say to open it and run `/argani:init` if it is not registered yet.
   Always pass the full path under `<artifact dir>` to `artifact_check.py`.
2. Artifact language: the language of this project's CLAUDE.md, else the user's. Only the
   prose is in that language. The `# Intent:` title prefix, the `##` section headings, file names,
   `Status:` lines, `AC-n`, `verify:` and verdict words always stay English.
3. Mode: it is `approve` only when `$ARGUMENTS` is exactly two tokens, `approve <slug>`, and the
   folder `<artifact dir>/<slug>/` exists. If `$ARGUMENTS` is exactly `approve <slug>` but the
   folder does not exist, say the slug was not found and stop; do not start an interview.
   Anything else is a description.

## Description mode

1. Interview the user briefly, a few questions at a time, only for what the description does
   not already answer:
   - What is the problem, and who is affected?
   - What constraints apply (policies, deadlines, compatibility)?
   - What does "better" look like?
   - How risky the change is: `low`, `medium` or `high` (it picks stronger models for the builder
     and the reviewers when high, cheaper ones when low).
   - For each success criterion: how will it be verified (a command, a test, or a named manual step)?
     When only a person can check it (judgement, data that stays local), write
     `verify: manual: <who does what>`.
2. Compute the slug: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py slug "<title>"`.
   If it fails (no ASCII letters or digits in the title), ask the user for an ASCII slug.
3. If `<artifact dir>/<slug>/intent.md` already exists, stop and ask before touching it.
4. Write it from `${CLAUDE_PLUGIN_ROOT}/templates/intent.md` with `Status: draft`. Replace every
   placeholder and delete guidance comments. Write `Risk: <level>` with the
   level the user chose; delete the line to keep `medium`. Every acceptance criterion must read
   `n. [ ] <claim> — verify: <how>`, numbered 1 to n in order; item n is AC-n when you refer to
   it. Do not invent criteria the user has not confirmed; list unknowns under Open questions.
5. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py intent <file>`; fix the file until
   it prints `VALID`.
6. Tell the user to review and correct the file, then run `/argani:intent approve <slug>`.

## Approve mode

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py status <artifact dir>/<slug>/intent.md`.
   - Non-zero exit: refuse, show the violations verbatim, never set the approved status.
   - Prints `approved`: say it is already approved and stop.
2. Take the approver's name from the user's message, else ask for it (one line, no guessing).
3. Run `date +%F`, then replace the Status line with
   `Status: approved by <name> on <YYYY-MM-DD>`.
4. Run `artifact_check.py status` again; it must print `approved`. If not, restore `Status: draft`
   and show the violations.
5. Say what comes next: `/argani:spec <slug>`.
