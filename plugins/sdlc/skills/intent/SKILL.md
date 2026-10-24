---
name: intent
description: Write or approve an intent.md, the first artifact of the sdlc loop. Use when the user wants to start a new piece of work, describe a problem or goal, or approve an intent. Slash form /sdlc:intent <description> or /sdlc:intent approve <slug>.
argument-hint: "<description> | approve <slug>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git config *), Bash(date *), Read, Write, Edit, Glob
---

# /sdlc:intent

Background on the loop, statuses and rules: `../../docs/sdlc.md`. This skill never writes code.

## Setup

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py` and read `artifactRoot` from the JSON.
2. Artifact language: the language of this repository's CLAUDE.md, else the user's. File names,
   `Status:` lines, `AC-n`, `verify:` and verdict words always stay English.

## When `$ARGUMENTS` is a description

1. Interview the user briefly, a few questions at a time, only for what the description does not
   already answer:
   - What is the problem, and who is affected?
   - What constraints apply (policies, deadlines, compatibility)?
   - What does "better" look like?
   - For each success criterion: how will it be verified (a command, a test, or a named manual step)?
2. Compute the slug: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py slug "<title>"`.
3. If `<artifactRoot>/<slug>/intent.md` already exists, stop and ask before touching it.
4. Write `<artifactRoot>/<slug>/intent.md` from `${CLAUDE_PLUGIN_ROOT}/templates/intent.md` with
   `Status: draft`. Replace every placeholder and delete the guidance comments you no longer need.
   Every acceptance criterion must read `- AC-n: <claim> — verify: <how>`. Do not invent criteria
   the user has not confirmed; list unknowns under Open questions.
5. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py intent <file>` and fix the file until
   it prints `VALID`.
6. Tell the user to review and correct the file, then run `/sdlc:intent approve <slug>`.

## When `$ARGUMENTS` is `approve <slug>`

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/artifact_check.py intent <artifactRoot>/<slug>/intent.md`.
2. If it exits non-zero: refuse. Show the violations verbatim. Never set the approved status.
3. If it passes: get the name with `git config user.name` and today's date with `date +%F`, and
   replace the Status line with `Status: approved by <name> on <YYYY-MM-DD>`.
4. Say what comes next: `/sdlc:spec <slug>`.
