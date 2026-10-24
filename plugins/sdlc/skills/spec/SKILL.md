---
name: spec
description: Write or approve a spec.md from an approved intent, the second artifact of the sdlc loop. Use when an intent is approved and needs a design, or when a spec needs approval. Slash form /sdlc:spec <slug> or /sdlc:spec approve <slug>.
argument-hint: "<slug> | approve <slug>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git config *), Bash(date *), Read, Write, Edit, Glob, Grep
---

# /sdlc:spec

Background on the loop, statuses and rules: `../../docs/sdlc.md`. This skill never writes code.

## Setup

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py` and read `artifactRoot`.
2. Artifact language: the language of this repository's CLAUDE.md, else the user's. File names,
   `Status:` lines, `AC-n`, `verify:` and verdict words always stay English.

## When `$ARGUMENTS` is `<slug>`

1. Read `<artifactRoot>/<slug>/intent.md`. If its Status line is not
   `Status: approved by <name> on <YYYY-MM-DD>`, **stop**: name the file, say the intent is not
   approved, and tell the user to run `/sdlc:intent approve <slug>`. Do not write spec.md.
2. Read the repository's CLAUDE.md and the code or documents the intent touches.
3. Write `<artifactRoot>/<slug>/spec.md` from `${CLAUDE_PLUGIN_ROOT}/templates/spec.md`,
   `Status: draft`:
   - Approach, and rejected alternatives.
   - Affected areas, as concrete paths.
   - Acceptance criteria mapping: one row per AC from the intent, with a concrete way to verify it.
   - Flagged concerns: especially policies or constraints that conflict with each other or with the
     approach. Do not resolve a conflict silently; flag it.
   - Open questions carried forward from the intent, plus new ones.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py spec <file>` and fix until `VALID`.
5. Remind the user that the human reviews the spec and does not write it: correct it by comment or
   edit, then run `/sdlc:spec approve <slug>`.

## When `$ARGUMENTS` is `approve <slug>`

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py spec <artifactRoot>/<slug>/spec.md`.
2. If it exits non-zero: refuse and show the violations verbatim. Never set the approved status.
3. If it passes: get the name with `git config user.name` and the date with `date +%F`, and replace
   the Status line with `Status: approved by <name> on <YYYY-MM-DD>`.
4. Say what comes next: `/sdlc:plan <slug>`.
