---
name: factory
description: Run an argani job end to end with fresh subagents (spec, build, review rounds, decision) and stop at a human gate or at the merge request. Also takes a human rework note. Slash form /argani:factory <slug> or /argani:factory rework <slug> <note>.
argument-hint: "<slug> | rework <slug> <note>"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Agent, Skill, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git *)
---

# /argani:factory

This session is the orchestrator. Loop, roles, protocol: `${CLAUDE_PLUGIN_ROOT}/docs/argani.md` and
`${CLAUDE_PLUGIN_ROOT}/docs/review-protocol.md`. It never edits code and never writes `intent.md`,
`spec.md`, `plan.md`, `build.md`, `review-<checklist>.md` or `decision.md`; agents do. Its own files:
`mr.md` and, for `rework`, `review-human.md`. Plugin root below = the value of `${CLAUDE_PLUGIN_ROOT}`.

Commits: invoking `/argani:factory` is the human's explicit instruction to make the commits this skill
describes on the job branch (the orchestrator's record commits and the builder's commits), and no
others. It never pushes without `mrCommand` and never merges. Repositories whose rules forbid commits
without a separate instruction per commit should use the manual loop (`/argani:spec`, `/argani:plan`,
`/argani:review`) instead.

Tools: the list above is the minimum, no `Bash(*)`. `mrCommand` runs through `Bash`, which the human
permits when asked. Cost: one spec-writer, one builder per round, N reviewers per round, one approver;
use it for jobs with clear acceptance criteria.

## Step 1

1. Parse `$ARGUMENTS`:
   - empty: **stop** and print the usage `/argani:factory <slug> | rework <slug> <note>`;
   - first word `rework`: `rework <slug> <note>`;
   - exactly one word: `<slug>`;
   - anything else (a description of new work, not a slug): **stop** without writing anything. The
     factory only runs a job that already has an intent. Say: start with `/argani:intent <the text>`,
     then `/argani:intent approve <slug>`, then `/argani:factory <slug>`.
   If step 3 reports no job folder for a one-word argument, give the same advice with that word.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py`. If it exits non-zero, **stop** and show its
   error. If `verifyCommand` is empty or `reviewers` is empty, **stop**, name the project's `project.json` in the argani
   home (or `<toplevel>/.claude/argani.json` for a repository without a project) and suggest `/argani:init` when the file does not exist yet.
   Keep the JSON (call it the config).
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_state.py <slug>`. If it exits non-zero, **stop** and
   show its output. Print `stage` and `next`.

## Loop

The state JSON is the only truth. Re-run `factory_state.py` after **every** agent returns and after every
commit or file you write; never skip a stage from memory. **Stop (end the turn)** at every human gate and
terminal stage. Each seat (builder, one reviewer seat, approver) is spawned at most twice per invocation
(one retry when the state still shows it cut off or `partial`); after that, stop and say which seat failed.

| `stage`                                        | Action                                                                                                            |
|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| `needs-intent-approval`, `needs-spec-approval` | Stop. Print `next`.                                                                                               |
| `needs-spec`                                   | Spawn `argani:spec-writer`, then stop: "spec ready; `/argani:spec approve <slug>` then `/argani:factory <slug>`". |
| `needs-build`, `needs-rework`                  | Branch, record, spawn a **new** builder (below), then re-run state.                                               |
| `needs-review`                                 | Require `on_job_branch`, run review round `review_round`, record, re-run state.                                   |
| `needs-decision`                               | Require `on_job_branch`, spawn `argani:approver`, record, re-run state.                                           |
| `needs-mr`                                     | Require `on_job_branch`, create the MR (below), then stop.                                                        |
| `done`                                         | Say the job is done. Nothing else.                                                                                |
| `escalate`                                     | Say `needs-human` and print `next`. A human decides; `rework` is refused at round 3.                              |

`<branch>` below is the state's `branch`: the repository's `branchPattern` (default `feature/{slug}`)
with the slug and, for `{type}`, the intent's `Type:` filled in. `<base_branch>` is the state's
`base_branch`: `baseBranchByType` for that type, else `baseBranch`. Never build either name yourself.
"Require `on_job_branch`": if false, stop and say the session is on `<current_branch>`, not `<branch>`.
`partial` entries are cut-off files: say in that agent's prompt "the previous attempt was cut off;
overwrite the file completely". If `review:human` is partial, do not spawn anything: tell the human to
fix or delete `review-human.md`.

### Record (the orchestrator commits the job folder)

Only paths under `<job_dir>` are ever added. If `git -C <toplevel> status --porcelain -- <job_dir>` is
non-empty: `git -C <toplevel> add -- <job_dir>` then
`git -C <toplevel> commit -m "<message>" [--trailer "<trailer>" ...] -- <job_dir>`, with one `--trailer`
per entry of `commitTrailers`, `{model}` replaced by your own model name (for example
`Claude Opus 5.5`), and no other trailer or footer. `<message>` is `recordCommitMessage` with
`{slug}` replaced by the slug and `{what}` by `artifacts before build`, `round <N> reviews`,
`decision` or `merge request` (default `chore(argani): record <slug> <what>`). Also record before the
push in `needs-mr`, only while `on_job_branch` is true. The builder commits code, `plan.md`, `build.md`.

When the config sets `commitSkill`, record through that repository skill instead (Skill tool):
the unit is exactly the changed paths under `<job_dir>` and the intended subject is `<message>`;
follow the skill for staging, scope and trailers, and add no `commitTrailers` yourself. If the skill
refuses the unit or the subject, stop and show why; never fall back to a plain `git commit`.

### Models

Spawn every agent with `model` from the state's `models`: `models.spec-writer`, `models.builder`,
`models.approver`, and `models.reviewers.<checklist>` for each reviewer seat. They come from
`agentModels` for the job's `risk` (the intent's `Risk:` line, `medium` when absent). When a value is
`inherit`, leave `model` out.

The reviewers of a job are the state's `reviewers`, not the config's: a checklist scoped by
`reviewerPaths` runs only when the job's diff touches one of its paths.

### Spec-writer prompt

```
Plugin root: <plugin root>
Intent: <job_dir>/intent.md
Spec: <job_dir>/spec.md
Config: <the config JSON>
Language: <language of the repository's CLAUDE.md, else of the intent>
```

### Branch and builder

1. **Stop** if `current_branch` is `HEAD` (detached) or `dirty` is true (job-folder files do not count):
   ask the human to switch branch or commit/stash.
2. If `on_job_branch` is false: `git switch <branch>` if `git rev-parse --verify <branch>` succeeds,
   else `git switch -c <branch> <base_branch>`. If the switch fails, **stop** and show the error.
3. Re-run state; if `on_job_branch` is still false, **stop**. Only then Record (`artifacts before build`;
   never commit on any other branch), and spawn `argani:builder`:

```
Plugin root: <plugin root>
Slug folder: <job_dir>
Branch: <branch>
Verify command: <verifyCommand>
Commit skill: <commitSkill, or "none">
Commit trailers: <commitTrailers as configured, {model} left in, one per line, or "none">
Round: <review_round>
Findings to address: <job_dir>/review/round-<rework_from>/       (only when rework_from is not null;
                                                                for a human rework this is the round folder holding review-human.md)
```

4. If its reply starts with `STOPPED wrong branch` or `STOPPED commit skill`, **stop** and show it. After it returns, re-run state:
   if `dirty` is true, **stop** ("builder left uncommitted changes"). Otherwise continue the loop.

### Review round

Run steps 5 and 6 of `${CLAUDE_PLUGIN_ROOT}/skills/review/SKILL.md` for `N = review_round` and slug folder
`<job_dir>` (one message, all missing seats, wait for all, rerun a cut-off seat once). Seats already in
`rounds[].complete` for that round are not spawned again. Do not print its table.

### Approver

```
Plugin root: <plugin root>
Slug folder: <job_dir>
Round folder: <job_dir>/review/round-<review_round>/
Base branch: <base_branch>
Reviewers: <the state's reviewers, comma-separated>
Protected paths: <protectedPaths, comma-separated, or "none">
```

### Merge request (`needs-mr`)

Record first (only with `on_job_branch` true). Then:
- `mrCommand` configured: `git push -u origin <branch>`, then `mrCommand` with `{branch}` replaced by
  `<branch>` and `{base}` by `<base_branch>`. If either fails, stop and show the error (no `mr.md`). On success write `<job_dir>/mr.md`
  (output or URL, branch, today's date), commit it (Record with `{what}` = `merge request`, local only),
  and stop: "MR ready for human review".
- Not configured: do **not** push. Stop and print `git push -u origin <branch>` and "open a merge
  request from <branch> into <base_branch>"; the human writes `mr.md` (URL and branch) or
  configures `mrCommand` and re-runs.

In both cases, when `decision.md` has `## Human verification before merge`, copy that checklist into
`mr.md` and into the final message: the human does those steps and ticks them before merging.

## `rework <slug> <note>`

1. Allowed only when `stage` is `needs-decision` and `round` is 1 (after a clean round 1, before a
   decision). Otherwise refuse and say why: decision or `mr.md` exists, the two-round cap is reached
   (the hook also denies `round-3`), or open findings go through the normal loop.
2. Write `<job_dir>/review/round-2/review-human.md`: line 1 `CHANGES <short summary>`, a blank line,
   the note as `- [Important] ...`, a blank line, `=== END OF REVIEW ===`.
3. Re-run state (`needs-rework`) and continue the loop.
