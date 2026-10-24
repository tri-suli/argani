---
name: plan
description: Write plan.md from an approved spec, the gate before any change in manual mode. Use when a spec is approved and the user is ready to plan the work. Slash form /sdlc:plan <slug>.
argument-hint: "<slug>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Write, Edit, Glob, Grep
---

# /sdlc:plan

Background on the loop, statuses and rules: `../../docs/sdlc.md`. This skill writes only plan.md;
it never changes code or documents outside the artifact folder.

## Setup

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py` and read `artifactRoot`.
2. Artifact language: the language of this repository's CLAUDE.md, else the user's. File names and
   `AC-n` stay English.

## Steps

1. Read `<artifactRoot>/<slug>/spec.md`. If its Status line is not
   `Status: approved by <name> on <YYYY-MM-DD>`, **stop**: name the file, say the spec is not
   approved, and tell the user to run `/sdlc:spec approve <slug>`. Do not write plan.md.
2. Recommend running this skill in plan mode so nothing outside the artifact folder can change
   while planning.
3. Read the spec's affected areas in the repository, then write `<artifactRoot>/<slug>/plan.md`
   from `${CLAUDE_PLUGIN_ROOT}/templates/plan.md`:
   - Files that change, each with a reason.
   - Order of work, in steps small enough to commit one by one.
   - Risks and how each is contained.
   - Proof: which check proves each AC from the spec. Every AC must appear.
4. Tell the user that in manual mode the plan is the gate before any code or document changes:
   work starts only after the human has read and accepted plan.md.
