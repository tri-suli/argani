---
name: factory
description: Run an argani job end to end with fresh subagents (spec, build, review rounds, decision) and stop at a human gate or at the merge request. Also takes a human rework note. Slash form /argani:factory <slug> [in <dir>] or /argani:factory rework <slug> [in <dir>] <note>.
argument-hint: "<slug> [in <dir>] | rework <slug> [in <dir>] <note>"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Agent, Skill, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# /argani:factory

This session is the orchestrator. Loop, roles, protocol: `${CLAUDE_PLUGIN_ROOT}/docs/argani.md` and
`${CLAUDE_PLUGIN_ROOT}/docs/review-protocol.md`. It never edits code and never writes `intent.md`,
`spec.md`, `plan.md`, `build.md`, `review-<checklist>.md` or `decision.md`; agents do. Its own files:
`mr-body.md` (written by `mr_description.py`), `mr.md`, `review/round-<N>/change.diff` (written by
`capture_change.py`) and, for `rework`, `review-human.md`. Plugin root below = the value of
`${CLAUDE_PLUGIN_ROOT}`.

Version control is the project's business, not argani's. Before `/argani:factory` the human (or the
project's own skills) prepares the place where the work happens, for example the branch or the
worktree, and either starts this session in that directory or passes it as `in <dir>`. Starting the
session there is simpler: with `in <dir>`, Claude Code also loads the session directory's `CLAUDE.md`
and rules into every agent, so the agents see two copies and apply the working directory's. The
agents run every command, project skills included, from the working directory. A working directory nested inside the registered path (for example
`.worktrees/<slug>`) must be covered by a `paths` pattern in `project.json` (`docs/config.md`),
otherwise the project root is the outer checkout and `diffCommand` and `protectedPaths` use the wrong
root. argani creates, switches, commits, pushes and merges nothing; the agents follow
the project's protocols (`CLAUDE.md`, its `@` imports, `.claude/rules`), the builder for commits too.

Tools: the list above is the minimum, no `Bash(*)`. `mrCommand` runs through `Bash`, which the human
permits when asked. Cost: one spec-writer, one builder per round, N reviewers per round, one approver;
use it for jobs with clear acceptance criteria. Projects that want a human at every step use the
manual loop (`/argani:spec`, `/argani:plan`, `/argani:review`) instead.

## Step 1

1. Parse `$ARGUMENTS`. `in <dir>` is recognised only immediately after the slug: words 2 and 3 of
   `<slug> in <dir>`, words 3 and 4 of `rework <slug> in <dir> <note>`. Everything after that is the
   note, whatever words it contains. `<dir>` is a single token without spaces: absolute, or relative
   to the session directory (`~` is expanded by the shell). It is **the working directory** and is
   `<dir>` below; without it `<dir>` is `.`, the directory the session runs in. Every command and
   agent below uses it. After the optional `in <dir>`:
   - empty: **stop** and print the usage `/argani:factory <slug> [in <dir>] | rework <slug> [in <dir>] <note>`;
   - first word `rework`: `rework <slug> <note>`;
   - exactly one word: `<slug>`;
   - anything else (a description of new work, not a slug): **stop** without writing anything. The
     factory only runs a job that already has an intent. Say: start with `/argani:intent <the text>`,
     then `/argani:intent approve <slug>`, then `/argani:factory <slug>`.
   If step 3 reports no job folder for a one-word argument, give the same advice with that word.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py <dir>`. If it exits non-zero (`<dir>` is not a directory or the
   config is invalid), **stop** and show its error. If `verifyCommand`, `diffCommand` or `reviewers` is empty, **stop**, name the project's
   `project.json` in the argani home and suggest `/argani:init` when the file does not exist yet.
   Keep the JSON (call it the config).
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_state.py <slug> <dir>`. If it exits non-zero, **stop** and
   show its output ("No job folder" can mean the working directory is outside the job's project). Print `stage` and `next`. Read `project`, `job_dir` and `directory` (the absolute working directory;
   use it wherever a prompt below says `<absolute working directory>`) from it and use them below.
   When `in <dir>` was given and `directory` differs from the session directory, print one line before
   spawning the first agent: "working directory differs from the session directory; the agents run every command, project skills included, from the working directory".

Commands: run each command on its own, so the allowed-tools patterns match and the human is not
prompted.

## Loop

The state JSON is the only truth. Re-run `factory_state.py` after **every** agent returns and after every
file you write; never skip a stage from memory. **Stop (end the turn)** at every human gate and
terminal stage. Each seat (builder, one reviewer seat, approver) is spawned at most twice per invocation
(one retry when the state still shows it cut off or `partial`); after that, stop and say which seat failed.

| `stage`                                        | Action                                                                                                            |
|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| `needs-intent-approval`, `needs-spec-approval` | Stop. Print `next`.                                                                                               |
| `needs-spec`                                   | Spawn `argani:spec-writer`, then stop: "spec ready; `/argani:spec approve <slug>` then `/argani:factory <slug>`". |
| `needs-build`, `needs-rework`                  | Spawn a **new** builder (below), then re-run state.                                                               |
| `needs-review`                                 | Run review round `review_round` (below), then re-run state.                                                       |
| `needs-decision`                               | Spawn `argani:approver` (below), then re-run state.                                                               |
| `needs-mr`                                     | Create the MR (below), then stop.                                                                                 |
| `done`                                         | Say the job is done and print `next`. Terminal: nothing else, argani never merges.                                |
| `escalate`                                     | Say `needs-human` and print `next`. A human decides; `rework` is refused at round 3.                              |

`partial` entries are cut-off files: say in that agent's prompt "the previous attempt was cut off;
overwrite the file completely". If `review:human` is partial, do not spawn anything: tell the human to
fix or delete `review-human.md`.

### Models

Spawn every agent with `model` from the state's `models`: `models.spec-writer`, `models.builder`,
`models.approver`, and `models.reviewers.<checklist>` for each reviewer seat. They come from
`agentModels` for the job's `risk` (the intent's `Risk:` line, `medium` when absent). When a value is
`inherit`, leave `model` out.

The reviewers of a job are the state's `reviewers`, not the config's: a checklist scoped by
`reviewerPaths` runs only when the captured `change.diff` touches one of its paths.

### Spec-writer prompt

```
Plugin root: <plugin root>
Working directory: <absolute working directory>
Intent: <job_dir>/intent.md
Spec: <job_dir>/spec.md
Config: <the config JSON>
Language: <language of the project's CLAUDE.md, else of the intent>
```

### Builder

Spawn `argani:builder` with the prompt below. It works in the working directory. Fill `<slug>` and
today's date in the `Instruction` line.

```
Plugin root: <plugin root>
Working directory: <absolute working directory>
Slug folder: <job_dir>
Verify command: <verifyCommand>
Round: <review_round>
Instruction: the human ran /argani:factory <slug> on <YYYY-MM-DD>; this run is their instruction for the work of this job, including the steps the project's protocols assign to the builder (for example the commit of its own work), inside the working directory. It authorises nothing else.
Findings to address:                                              (only when rework_from is not null)
- <job_dir>/review/round-<rework_from>/review-<checklist>.md      (one path per review file in that round
- <job_dir>/review/round-<rework_from>/review-human.md             folder, from the state's rounds[].present;
                                                                    a human rework has review-human.md)
```

After it returns, re-run state and continue the loop. Its reply is one line; if `build` is still not
`complete`, the retry rule above applies.

### Review round

1. If `rounds` has no entry for `review_round` with a `review-<checklist>.md` in its `present` (the
   human note does not count), run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture_change.py <slug> <dir>`.
   It runs `diffCommand` with the project root of the working directory as its working directory and writes
   `<job_dir>/review/round-<review_round>/change.diff`. If it exits non-zero, **stop** and show its
   output. If its `bytes` is 0, **stop** and say "diffCommand printed nothing; nothing to review.
   Check diffCommand against the builder's commit rule" (committed work and a working tree need different commands). Re-run state, because the captured `files`
   may narrow the `reviewers` (`reviewerPaths`). When the round already has a review file, the change
   is fixed: do not capture again, the existing `change.diff` stays.
2. Run steps 4 to 6 of `${CLAUDE_PLUGIN_ROOT}/skills/review/SKILL.md` for `N = review_round` and slug
   folder `<job_dir>` (one message, all missing seats, wait for all, rerun a cut-off seat once). Seats
   already in `rounds[].complete` for that round are not spawned again. Do not print its table.

### Approver

```
Plugin root: <plugin root>
Slug folder: <job_dir>
Round folder: <job_dir>/review/round-<review_round>/
Change: <job_dir>/review/round-<review_round>/change.diff
Reviewers: <the state's reviewers, comma-separated>
Protected paths: <protectedPaths, comma-separated, or "none">
```

Before spawning the approver, check that `change.diff` exists in the round folder. If it is missing (a
round reviewed before 2.0.0), run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture_change.py <slug> <dir>`:
at `needs-decision` it writes the missing file and refuses to overwrite an existing one. Apply the
same empty-output rule as above, then spawn the approver.

### Merge request (`needs-mr`)

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mr_description.py <slug> <dir> --write`. If it exits non-zero, stop and
   show its output. It writes `<job_dir>/mr-body.md` (acceptance criteria of `intent.md`, human
   verification checklist of `decision.md`, where the task folder is) and prints JSON with `title`,
   `bodyFile`, `directory` and, when `mrCommand` is configured, `command`.
- `mrCommand` configured: run the printed `command` verbatim (it starts with `cd` into the working directory); never rebuild or re-quote it. If it
  fails, stop and show the error (no `mr.md`). Otherwise write `<job_dir>/mr.md` (the command's
  output or URL, and today's date) and stop: "MR ready for human review".
- Not configured: print `title` and `bodyFile` and tell the human to open the merge request with
  that description in their own way, then write `mr.md` (the URL) or configure `mrCommand` and re-run.

In both cases, when `decision.md` has `## Human verification before merge`, copy that checklist into
`mr.md` and into the final message: the human does those steps and ticks them before merging. When the
merge request is merged, the human adds a line `Merged: <YYYY-MM-DD>` to `mr.md`; the board then shows the
task as Done. argani itself never pushes, merges or commits.

## `rework <slug> <note>`

1. Allowed only when `stage` is `needs-decision` and `round` is 1 (after a clean round 1, before a
   decision). Otherwise refuse and say why: decision or `mr.md` exists, the two-round cap is reached
   (the hook also denies `round-3`), or open findings go through the normal loop.
2. Write `<job_dir>/review/round-2/review-human.md`: line 1 `CHANGES <short summary>`, a blank line,
   the note as `- [Important] ...`, a blank line, `=== END OF REVIEW ===`.
3. Re-run state (`needs-rework`) and continue the loop.
