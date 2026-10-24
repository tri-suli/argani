---
name: factory
description: Run an sdlc job end to end with fresh subagents (spec, build, review rounds, decision) and stop at a human gate or at the merge request. Also takes a human rework note. Slash form /sdlc:factory <slug> or /sdlc:factory rework <slug> <note>.
argument-hint: "<slug> | rework <slug> <note>"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Agent, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git *)
---

# /sdlc:factory

This session becomes the orchestrator. Loop, roles and protocol: `../../docs/sdlc.md` and
`../../docs/review-protocol.md`. The orchestrator never edits code and never writes `intent.md`,
`spec.md`, `plan.md`, `build.md`, `review/round-*/review-<checklist>.md` or `decision.md`; agents do.
Its own files are `mr.md` and, for `rework`, `review-human.md`.

Tools: the list above is the minimum. `mrCommand` (configured per repo, e.g. `gh pr create ...`) is run
with `Bash`, which the human must permit when the session asks; the skill does not grant `Bash(*)`.

Cost: one spec-writer, one builder per round, N reviewers per round, one approver. Use it only for jobs
with clear acceptance criteria.

## Step 0: preconditions

1. Parse `$ARGUMENTS`: `<slug>`, or `rework <slug> <note>`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py`. If `verifyCommand` is empty or
   `reviewers` is empty, **stop** and say which key is missing in `<toplevel>/.claude/sdlc.json`.
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_state.py <slug>`. If it exits 1, stop and say
   there is no job folder. Print `stage` and `next`.

## Loop

The JSON from `factory_state.py` is the only state. Re-run it after **every** agent returns and after
every file you write, and act on the new `stage`. Never skip a stage from memory. **Stop (end the
turn)** at every human gate and terminal stage below.

| `stage` | Action |
|---|---|
| `needs-intent-approval` | Stop. Print `next` (the approve command). |
| `needs-spec` | Spawn `sdlc:spec-writer` (prompt below). Then stop: "spec ready; `/sdlc:spec approve <slug>` then `/sdlc:factory <slug>`". |
| `needs-spec-approval` | Stop. Print `next`. |
| `needs-build`, `needs-rework` | Prepare the branch, spawn a **new** `sdlc:builder`, then continue straight to review. |
| `needs-review` | Run review round `review_round`, then re-run state. |
| `needs-decision` | Spawn `sdlc:approver`, then re-run state. |
| `needs-mr` | Create the merge request (below), then stop. |
| `done` | Say the job is done. Nothing else. |
| `escalate` | Say `needs-human` and print `next`. A human decides; `/sdlc:factory rework` is refused by the hook at round 3. |

If `partial` is non-empty, the seat is cut off: tell the agent in its prompt "the previous attempt was
cut off; overwrite the file completely".

### Spec-writer prompt

```
Intent: <job_dir>/intent.md
Write: <job_dir>/spec.md
Config: <toplevel>/.claude/sdlc.json
Template: ${CLAUDE_PLUGIN_ROOT}/templates/spec.md
Language: the language of this repository's CLAUDE.md, else the intent's. Status: draft.
```

### Branch and builder

1. If `dirty` is true, **stop** and ask the human to commit or stash (job-folder artifacts do not count).
2. If `on_job_branch` is false: `git switch sdlc/<slug>` when the branch exists
   (`git rev-parse --verify sdlc/<slug>`), else `git switch -c sdlc/<slug>` from the current HEAD.
3. Spawn `sdlc:builder` with:

```
Slug: <slug>   Slug folder: <job_dir>   Branch: sdlc/<slug> (commit on this branch only; never push or merge)
Read: <job_dir>/spec.md, <job_dir>/plan.md (if present)
Write: <job_dir>/plan.md (only if missing), <job_dir>/build.md, code, commits
Templates: ${CLAUDE_PLUGIN_ROOT}/templates/plan.md, ${CLAUDE_PLUGIN_ROOT}/templates/build.md
verifyCommand: <verifyCommand>
Address: <job_dir>/review/round-<rework_from>/  (omit when rework_from is null)
```

   When `rework_from` is set, tell it to append `## Rework after round <rework_from>` to `build.md`
   (state uses that heading to know the round was addressed).

### Review round

Run steps 5 and 6 of `../review/SKILL.md` (spawn every `sdlc:reviewer` in one
message, wait for all, rerun a cut-off seat once), skipping its steps 1 to 4 and using `review_round` as `N` and the slug folder
`job_dir`. Do not print its table; re-run state and continue the loop.

### Approver

Spawn `sdlc:approver` with: slug folder `<job_dir>`, latest round folder `<job_dir>/review/round-<round>/`,
`build.md`, `spec.md`, `plan.md` in it, config `<toplevel>/.claude/sdlc.json`, default branch `<default_branch>`.

### Merge request (`needs-mr`)

- `mrCommand` configured: `git push -u origin sdlc/<slug>`, then run `mrCommand` with `{branch}`
  replaced by `sdlc/<slug>`. If either fails, stop and show the error (write no `mr.md`). On success
  write `<job_dir>/mr.md`: the command output or URL, the branch, and today's date. Stop: "MR ready
  for human review".
- Not configured: do **not** push. Stop and print `git push -u origin sdlc/<slug>` plus "open a
  merge request from sdlc/<slug> into <default_branch>", and tell the human to write `mr.md` (URL
  and branch) or configure `mrCommand` and re-run `/sdlc:factory <slug>`.

## `rework <slug> <note>`

1. Run state. Allowed only when `stage` is `needs-decision` and `round` is 1. Otherwise refuse and say
   why: a decision or `mr.md` exists, or the two-round cap is reached (the hook also denies `round-3`),
   or open reviewer findings must be reworked through the normal loop first.
2. Write `<job_dir>/review/round-<round+1>/review-human.md`: line 1 `CHANGES <short note summary>`,
   a blank line, the note as `- [Important] ...`, a blank line, `=== END OF REVIEW ===`.
3. Re-run state (it reports `needs-rework`) and continue the loop.
