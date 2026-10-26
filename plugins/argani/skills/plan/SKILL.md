---
name: plan
description: Write or approve plan.md from an approved spec, the gate before any change in manual mode. Use when a spec is approved and the user is ready to plan the work, or when a plan needs approval. Slash form /argani:plan <slug> or /argani:plan approve <slug>.
argument-hint: "<slug> | approve <slug>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git config user.name), Bash(date +%F), Read, Write, Edit, Glob, Grep
---

# /argani:plan

Background on the loop, statuses and rules: `${CLAUDE_PLUGIN_ROOT}/docs/argani.md`.
This skill writes only plan.md; it never changes code or documents outside the artifact folder.

## Setup

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If it fails, show its error and stop.
   Read `toplevel` and `artifactRoot`. Artifacts live in `<toplevel>/<artifactRoot>/<slug>/`;
   use the current directory when `toplevel` is null.
2. Artifact language: the language of this repository's CLAUDE.md, else the user's. Only the
   prose is in that language. The `# Plan:` title prefix, the `##` section headings, file names,
   `Status:` lines and `AC-n` always stay English.
3. Mode: it is `approve` only when `$ARGUMENTS` is exactly two tokens, `approve <slug>`, and the
   folder `<artifact dir>/<slug>/` exists. Otherwise `$ARGUMENTS` is the `<slug>`.

## Write mode

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py status <artifact dir>/<slug>/spec.md`.
   - Non-zero exit: stop and show the violations.
   - Prints `draft`: **stop**. Name the file, say the spec is not approved, and tell the user to
     run `/argani:spec approve <slug>`. Do not write plan.md.
2. If `plan.md` already exists in that folder, stop and ask before touching it.
3. Planning can be thought through in plan mode if the user likes; write plan.md after leaving
   plan mode, since plan mode does not allow writing files.
4. Read the spec's affected areas in the repository, then write `plan.md` from
   `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` with `Status: draft`:
   - Files that change, each with a reason.
   - Order of work, in steps small enough to commit one by one.
   - Risks and how each is contained.
   - Proof: which check proves each AC from the spec. Every AC must appear.
5. Run `artifact_check.py plan <file>`; fix until `VALID`.
6. Tell the user that in manual mode the plan is the gate before any code or document changes:
   work starts only after the human has read plan.md and run `/argani:plan approve <slug>`.

## Approve mode

1. Run `artifact_check.py status <plan.md>`.
   - Non-zero exit: refuse, show the violations verbatim, never set the approved status.
   - Prints `approved`: say it is already approved and stop.
2. Run `git config user.name`. If it is empty, stop and ask the user to set it.
3. Run `date +%F`, then replace the Status line with
   `Status: approved by <user.name> on <YYYY-MM-DD>`.
4. Run `artifact_check.py status` again; it must print `approved`. If not, restore `Status: draft`
   and show the violations.
5. Say that work may now start.
