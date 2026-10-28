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
`mr-body.md` (written by `mr_description.py`), `mr.md` and, for `rework`, `review-human.md`. Plugin root below = the value of `${CLAUDE_PLUGIN_ROOT}`.

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
   show its output. Print `stage` and `next`. Read `project`, `job_dir`, `job_dir_in_repo` and
   `record_dir` from it and use them below.

Commands: run each command on its own. Never chain with `&&` or `;` and never `cd` first (use
`git -C`), so the allowed-tools patterns match and the human is not prompted.

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

Only paths under `<job_dir>` (and, for a registered project, its `project.json`) are ever added.

**Registered project (`project` is set).** The job folder is recorded in the argani home's own git
repository, `<record_dir>` (the state's `home`), never in the project repository, so it does not depend
on the project repository's branch. If `git -C <record_dir> status --porcelain -- <job_dir>` is non-empty:
`git -C <record_dir> add -- <job_dir> projects/<project>/project.json` then
`git -C <record_dir> commit -q -m "argani: record <project>/<slug> <what>" -- <job_dir> projects/<project>/project.json`,
with `<what>` one of `artifacts before build`, `build`, `round <N> reviews`, `decision`, `merge request`. The message is fixed: no trailers, no `commitSkill` (the home has no commit
rules); `recordCommitMessage`, `commitTrailers` and `commitSkill` govern only the legacy record below
and the builder's code commits. Record before the push in `needs-mr` too, and right after the builder
returns (`<what>` = `build`), since the builder does not commit `plan.md` and `build.md` here.
`<job_dir>` is absolute; the `project.json` pathspec is relative to `<record_dir>`. Unrelated changes
in the home are left alone: `commit -- <paths>` commits only those paths. If add or commit fails (for
example no git `user.name`/`user.email` in the home), stop and show the error.
If `record_repo_ok` is false (the home is not a repository of its own, so git would use a parent
repository), run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_home.py --create` once and re-run
state; if it is still false, stop and show the state.

**Repository without a project (legacy).** If `git -C <toplevel> status --porcelain -- <job_dir>` is
non-empty: `git -C <toplevel> add -- <job_dir>` then
`git -C <toplevel> commit -m "<message>" [--trailer "<trailer>" ...] -- <job_dir>`, with one `--trailer`
per entry of `commitTrailers`, `{model}` replaced by your own model name (for example
`Claude Opus 5.5`), and no other trailer or footer. `<message>` is `recordCommitMessage` with
`{slug}` replaced by the slug and `{what}` by `artifacts before build`, `round <N> reviews`,
`decision` or `merge request` (default `chore(argani): record <slug> <what>`). Also record before the
push in `needs-mr`, only while `on_job_branch` is true. The builder commits code, and `plan.md` and
`build.md` too when `job_dir_in_repo` is true; otherwise the Record step above covers them.

When the config sets `commitSkill`, record a legacy job through that repository skill instead (Skill tool):
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
   a legacy job is never committed on any other branch), and spawn `argani:builder`:

```
Plugin root: <plugin root>
Slug folder: <job_dir>
Job folder in repository: <yes when job_dir_in_repo is true, else no>
Branch: <branch>
Verify command: <verifyCommand>
Commit skill: <commitSkill, or "none">
Commit trailers: <commitTrailers as configured, {model} left in, one per line, or "none">
Round: <review_round>
Findings to address: <job_dir>/review/round-<rework_from>/       (only when rework_from is not null;
                                                                for a human rework this is the round folder holding review-human.md)
```

4. If its reply starts with `STOPPED wrong branch` or `STOPPED commit skill`, **stop** and show it. After it returns, re-run state:
   if `dirty` is true, **stop** ("builder left uncommitted changes"). Otherwise, for a registered project, Record (`build`), then continue the loop.

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

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mr_description.py <slug> --write`. If it exits non-zero, stop and
   show its output. It writes `<job_dir>/mr-body.md` (acceptance criteria of `intent.md`, human
   verification checklist of `decision.md`, where the task folder is) and prints JSON with `title`,
   `bodyFile` and, when `mrCommand` is configured, `command`. `mr-body.md` is an artifact of the job
   folder and is recorded with it.
2. Record (for a legacy job only with `on_job_branch` true), so `mr-body.md` is committed before the push.
- `mrCommand` configured:
  3. `git push -u origin <branch>`.
  4. Run the printed `command` verbatim; never rebuild or re-quote it.
  If 3 or 4 fails, stop and show the error (no `mr.md`).
  5. Write `<job_dir>/mr.md` (output or URL, branch, base, today's date).
  6. Record again (`{what}` = `merge request`, local only) and stop: "MR ready for human review".
- Not configured: do **not** push. Print `title`, `bodyFile` and tell the human to push `<branch>`,
  open a merge request from `<branch>` into `<base_branch>` with that description, then write `mr.md`
  (URL and branch) or configure `mrCommand` and re-run.

In both cases, when `decision.md` has `## Human verification before merge`, copy that checklist into
`mr.md` and into the final message: the human does those steps and ticks them before merging.

## `rework <slug> <note>`

1. Allowed only when `stage` is `needs-decision` and `round` is 1 (after a clean round 1, before a
   decision). Otherwise refuse and say why: decision or `mr.md` exists, the two-round cap is reached
   (the hook also denies `round-3`), or open findings go through the normal loop.
2. Write `<job_dir>/review/round-2/review-human.md`: line 1 `CHANGES <short summary>`, a blank line,
   the note as `- [Important] ...`, a blank line, `=== END OF REVIEW ===`.
3. Re-run state (`needs-rework`) and continue the loop.
