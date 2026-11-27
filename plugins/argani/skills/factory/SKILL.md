---
name: factory
description: Run an argani job autonomously from a one-sentence description (or an existing slug) through intake, spec, build, review rounds, decision, merge request and the project's merge command, stopping only when a human must answer. Also takes a human answer, rework note, cancel or revision. Slash form /argani:factory [in <dir>] <description>, /argani:factory <slug> [in <dir>], /argani:factory answer <slug> [in <dir>] <answer>, /argani:factory rework <slug> [in <dir>] <note>, /argani:factory cancel <slug> [in <dir>] [<reason>] or /argani:factory revise <slug> [in <dir>] <note>.
argument-hint: "[in <dir>] <description> | <slug> [in <dir>] | answer <slug> [in <dir>] <answer> | rework <slug> [in <dir>] <note> | cancel <slug> [in <dir>] [<reason>] | revise <slug> [in <dir>] <note>"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Agent, Skill, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# /argani:factory

This session is the orchestrator. Loop, roles, protocol: `${CLAUDE_PLUGIN_ROOT}/docs/argani.md` and
`${CLAUDE_PLUGIN_ROOT}/docs/review-protocol.md`. It never edits code and never writes `intent.md`,
`spec.md`, `plan.md`, `build.md`, `review-<checklist>.md` or `decision.md`; agents do. Its own files
(`answers.md`, `blocked.md`, the `Status:` line of intent and spec, `mr.md`, `review-human.md`) it
writes only through `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_actions.py <action> <slug> <dir> [args]`,
never by hand; it prints `{"ok": true, ...}` or exits 1 with the reason. Also its own: `mr-body.md`
(written by `mr_description.py`) and `review/round-<N>/change.diff` (written by `capture_change.py`).
Nobody approves their own work: intake and spec-writer write drafts, this session approves them.
Plugin root below = the value of `${CLAUDE_PLUGIN_ROOT}`.

Version control is the project's business, not argani's. Before `/argani:factory` the human (or the
project's own skills) prepares the place where the work happens, for example the branch or the
worktree, and either starts this session in that directory or passes it as `in <dir>`. Starting the
session there is simpler: with `in <dir>`, Claude Code also loads the session directory's `CLAUDE.md`
and rules into every agent, so the agents see two copies and apply the working directory's. The
agents run every command, project skills included, from the working directory. A working directory nested inside the registered path (for example
`.worktrees/<slug>`) must be covered by a `paths` pattern in `project.json` (`docs/config.md`),
otherwise the project root is the outer checkout and `diffCommand` and `protectedPaths` use the wrong
root. argani runs no version control itself; the merge is the project's `mergeCommand`. The agents follow
the project's protocols (`CLAUDE.md`, its `@` imports, `.claude/rules`), the builder for commits too.

Tools: the list above is the minimum, no `Bash(*)`. `mrCommand` and `mergeCommand` run through `Bash`,
which the human permits when asked. Cost: one intake, one spec-writer, one builder per round, N reviewers
per round, one approver; use it for jobs with clear acceptance criteria. Projects that want a human at every step use the
manual loop (`/argani:spec`, `/argani:plan`, `/argani:review`) instead.

## Step 1

1. Parse `$ARGUMENTS` (words split on spaces); check in this order, the first match wins:
   - empty: **stop** and print the usage `/argani:factory [in <dir>] <description> | <slug> [in <dir>] | answer <slug> [in <dir>] <answer> | rework <slug> [in <dir>] <note> | cancel <slug> [in <dir>] [<reason>] | revise <slug> [in <dir>] <note>`;
   - first word `answer`, `rework`, `cancel` or `revise`: `<word> <slug> [in <dir>] <text>` (the text of `cancel` is optional); words 3 and 4 are
     `in <dir>` when word 3 is `in`; everything after is the answer or note, whatever words it contains;
   - first word `in`: `in <dir> <description>`; words 1 and 2 are the working directory, the rest is the description
     (so "Fix typo in README" is never cut). A description takes `in <dir>` only here, never later;
   - exactly one word: `<slug>`;
   - exactly three words with `in` as word 2: `<slug> in <dir>` ONLY when ALL hold: `<dir>` is an existing directory,
     `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py <dir>` succeeds, and the task folder `<tasksDir>/<slug>/`
     exists (`tasksDir` from that config). If any fails, do NOT stop: the whole argument string is a description,
     so "Sign in fails" is a description;
   - anything else: the whole argument string is a `<description>` of new work; `<slug>` is known after step 2.
   `<dir>` is a single token without spaces (a trailing `,` or `.` is dropped, since users type `in <dir>, <note>`): absolute,
   or relative to the session directory (`~` is expanded by the shell). It is **the working directory** and is
   `<dir>` below; without it `<dir>` is `.`, the directory the session runs in. Every command and
   agent below uses it.
   Free text (a description, answer or note) is always passed to `factory_actions.py` as ONE shell-quoted argument.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py <dir>`. If it exits non-zero (`<dir>` is not a directory or the
   config is invalid), **stop** and show its error. If `verifyCommand`, `diffCommand` or `reviewers` is empty, **stop**, name the project's
   `project.json` in the argani home and suggest `/argani:init` when the file does not exist yet.
   Keep the JSON (call it the config).
3. A description: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_actions.py new <dir> "<description>"`.
   It creates the task folder with `description.md` and prints `{"ok": true, "slug": ..., "job_dir": ...}`;
   that is `<slug>`. If it refuses (the task exists: say to run `/argani:factory <slug>` to continue it or
   to pick another wording; no slug can be derived: ask for a wording with plain letters), **stop**.
   `answer <slug> <answer>`: run `factory_actions.py answer <slug> <dir> "<answer>"`; if it refuses (the task is not
   waiting for an answer), **stop** and show why.
   `rework <slug> <note>`: do step 4 first, then its section.
   `cancel <slug> [<reason>]`: stop an argani agent running for the task, run `factory_actions.py cancel <slug> <dir> "<reason>"`;
   if it refuses (`done` or `cancelled`), **stop** and show why. Then step 4 (the state is `cancelled`).
   `revise <slug> <note>`: do step 4 first, then its section.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_state.py <slug> <dir> --record`. If it exits non-zero, **stop** and
   show its output ("No job folder" can mean the working directory is outside the job's project; for a
   one-word argument say so and suggest `/argani:factory "<description>"`). Print `stage` and `next`. Read `project`, `job_dir` and `directory` (the absolute working directory;
   use it wherever a prompt below says `<absolute working directory>`) from it and use them below.
   When `in <dir>` was given and `directory` differs from the session directory, print one line before
   spawning the first agent: "working directory differs from the session directory; the agents run every command, project skills included, from the working directory".
   In that case also run once `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/instruction_drift.py <session directory> <directory>`;
   it prints `{"stale": [paths]}`. When `stale` is not empty, add the line `Stale session copies: <paths, comma-separated>` to
   the prompts of intake, spec-writer, builder, every reviewer seat, and approver (below); the agents then read those files from the
   working directory instead of trusting the copy this session loaded.
   Then continue with the loop (for `rework` and `revise`, run their section first; `cancel` is done in step 3).

Commands: run each command on its own, so the allowed-tools patterns match and the human is not
prompted.

## Loop

The state JSON is the only truth. After **every** agent returns and every action you run, run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_state.py <slug> <dir> --record` (it also appends the
stage to the task's history); never skip a stage from memory. Each seat (intake, spec-writer, builder, one reviewer seat, approver)
is spawned at most twice per invocation (one retry when the state still shows it cut off or `partial`);
after the second failure run `factory_actions.py block <slug> <dir> agent-failed "<seat>: <why>"` and
re-run the state (it shows `needs-human`). Act on the table until a stage says stop.

| `stage`                 | Action                                                                                                                                                                                                  |
|-------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `needs-intake`          | Spawn `argani:intake` ([prompt](#intake-prompt); add `Answers: <job_dir>/answers.md` when `answered`; add `Previous: <state.previous>` when `reason` is `revision` and `previous` is not null), then re-run state. |
| `needs-intent-approval` | `factory_actions.py approve <slug> <dir> intent`, then re-run state.                                                                                                                                    |
| `needs-spec`            | Spawn `argani:spec-writer` ([prompt](#spec-writer-prompt); add `Answers: <job_dir>/answers.md` when `answered`; add `Previous: <state.previous>` when `reason` is `revision` and `previous` is not null), then re-run state. |
| `needs-spec-approval`   | `factory_actions.py approve <slug> <dir> spec`, then re-run state.                                                                                                                                      |
| `needs-build`           | Spawn a **new** builder ([below](#builder)), then re-run state.                                                                                                                                         |
| `needs-rework`          | When `answered` and `human_note_round` is set: `factory_actions.py human-note <slug> <dir>` first. Then spawn a **new** builder, then re-run state.                                                     |
| `needs-review`          | Run review round `review_round` ([below](#review-round)), then re-run state.                                                                                                                            |
| `needs-decision`        | Spawn `argani:approver` ([below](#approver)), then re-run state.                                                                                                                                        |
| `needs-mr`              | [Merge request](#merge-request-needs-mr), then re-run state.                                                                                                                                            |
| `needs-merge`           | [Merge](#merge-needs-merge), then re-run state.                                                                                                                                                         |
| `needs-human`           | When `reason` is `mr-missing` or `merge-missing`, first apply the [self-recording rule](#self-recording-an-mr-or-a-merge-the-session-already-holds). Stop, unless that rule records an answer (then continue the loop). Before stopping, when `reason` is `mr-missing` and neither `mrCommand` nor `mrSkill` is configured, run `mr_description.py <slug> <dir> --write` so `mr-body.md` exists. Print `reason`, `question` and how to answer: `/argani:factory answer <slug> <answer>`, with the words from `next` (`PASS`, `FAIL <note>`, `MERGED`, `RETRY`, `CANCEL`, or free text) where they apply, as one short copyable line; add that the human can also just say it in chat. |
| `done`, `cancelled`     | Say so, print `next`. Terminal: stop.                                                                                                                                                                   |

`partial` entries are cut-off files: say in that agent's prompt "the previous attempt was cut off;
overwrite the file completely". If `review:human` is partial, do not spawn anything: tell the human to
fix or delete `review-human.md`.

### Models

Spawn every agent with `model` from the state's `models`: `models.intake`, `models.spec-writer`, `models.builder`,
`models.approver`, and `models.reviewers.<checklist>` for each reviewer seat. They come from
`agentModels` for the job's `risk` (the intent's `Risk:` line, `medium` when absent). When a value is
`inherit`, leave `model` out.

The reviewers of a job are the state's `reviewers`, not the config's: a checklist scoped by
`reviewerPaths` runs only when the captured `change.diff` touches one of its paths.

### Intake prompt

```
Plugin root: <plugin root>
Working directory: <absolute working directory>
Intent: <job_dir>/intent.md
Config: <the config JSON>
Language: <language of the project's CLAUDE.md, else of the description>
Description: <the content of <job_dir>/description.md; for an older task without it, the heading of intent.md>
Answers: <job_dir>/answers.md                          (only when the state says answered)
Previous: <state.previous>                             (only when previous is not null and reason is revision)
Stale session copies: <paths>                          (only when instruction_drift.py printed some)
```

### Spec-writer prompt

```
Plugin root: <plugin root>
Working directory: <absolute working directory>
Intent: <job_dir>/intent.md
Spec: <job_dir>/spec.md
Config: <the config JSON>
Language: <language of the project's CLAUDE.md, else of the intent>
Answers: <job_dir>/answers.md                          (only when the state says answered)
Previous: <state.previous>                             (only when previous is not null and reason is revision)
Stale session copies: <paths>                          (only when instruction_drift.py printed some)
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
Previous: <state.previous>                                        (only when <state.previous>/build.md exists)
Stale session copies: <paths>                                     (only when instruction_drift.py printed some)
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
   folder `<job_dir>` (one message, all missing seats, wait for all, rerun a cut-off seat once); when stale copies were found,
   each seat's prompt also gets the `Stale session copies:` line. Seats
   already in `rounds[].complete` for that round are not spawned again. Do not print its table.

### Approver

```
Plugin root: <plugin root>
Slug folder: <job_dir>
Round folder: <job_dir>/review/round-<review_round>/
Change: <job_dir>/review/round-<review_round>/change.diff
Reviewers: <the state's reviewers, comma-separated>
Protected paths: <protectedPaths, comma-separated, or "none">
Working directory: <absolute working directory>                   (only with the next line)
Stale session copies: <paths>                                     (only when instruction_drift.py printed some)
```

Before spawning the approver, check that `change.diff` exists in the round folder. If it is missing (a
round reviewed before 2.0.0), run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture_change.py <slug> <dir>`:
at `needs-decision` it writes the missing file and refuses to overwrite an existing one. Apply the
same empty-output rule as above, then spawn the approver.

### Merge request (`needs-mr`)

- First run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture_change.py <slug> <dir> --check-drift` (a commit made after APPROVE must be
  reviewed). It prints `{"drift": ...}`. When `drift` is true, re-run state with `--record` (it is now `needs-review`) and continue the loop
  instead of creating the merge request. `{"drift": false, "unknown": true}` (the approved round has no `change.diff`) or `"empty": true`:
  continue. If it exits non-zero, **stop** and show its output.
- `answer` of the state is not null (a human gave the merge request URL): `factory_actions.py mr <slug> <dir> "<state.answer>"`.
- Otherwise (including after a `PASS` of the manual verification): `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mr_description.py <slug> <dir> --write`. If it exits non-zero, stop and
  show its output. It writes `<job_dir>/mr-body.md` (acceptance criteria of `intent.md`, human
  verification checklist of `decision.md`) and prints JSON with `title` (the intent heading, or the output of `mrTitleCommand` when configured),
  `bodyFile`, `directory`, `titleSource` and, when `mrCommand` is configured, `command`, or, when `mrSkill` is configured, `skill`.
  With `command`: run it verbatim with Bash (it starts with `cd` into the working directory); never rebuild or re-quote it.
  With `skill`: invoke that project skill with the Skill tool, passing the working directory (`directory`), the title and the path
  `bodyFile` as material the skill may use under the project's own conventions; take the merge request URL from the skill's result
  or tool output; then run `factory_actions.py mr <slug> <dir> "<the merge request url>"` (the URL and the branch, not the skill's whole output).
  On failure `block ... mr-missing "<short reason>"`.
  On success: `factory_actions.py mr <slug> <dir> "<its output>"`. On failure:
  `factory_actions.py block <slug> <dir> mr-missing "<short stderr>"`. Without `mrCommand` the state is
  already `needs-human` (`mr-missing`) and this section is not reached (neither `mrCommand` nor `mrSkill`): there, first run
  `mr_description.py <slug> <dir> --write` so `mr-body.md` exists, then print the question.

When the printed `warnings` is non-empty, repeat them in the final message to the human.

### Merge (`needs-merge`)

- When `previous` is not null and `<job_dir>/mr-body.md` is missing or older than the latest `revisions/<n>/` folder, the merge request
  description is stale: run `mr_description.py <slug> <dir> --write` to regenerate `mr-body.md` and update the description when the
  project has a way to (`mrCommand`, `mrSkill` or the project's own skills); otherwise say in the final message that it must be updated by hand.
- Without a `MERGED` answer, first run `capture_change.py <slug> <dir> --check-drift` as for the merge request; when `drift` is true,
  re-run state with `--record` and continue the loop instead of merging. With a `MERGED` answer run no check: a merge done outside
  argani cannot be reviewed. Never cancel a task while `mergeCommand` runs in the background.
- `answer_word` of the state is `MERGED` (the human merged it): `factory_actions.py merged <slug> <dir>`.
- `mergeSkill` is configured (the drift check above comes first): invoke that project skill with the Skill tool for the url in `mr.md`.
  Confirm the merge request is merged, from the skill's result or by asking the skill or the forge tool for its status (a merge only
  scheduled, such as auto-merge, is not merged); then
  `factory_actions.py merged <slug> <dir>`. Otherwise `factory_actions.py block <slug> <dir> merge-missing "<short reason>"`.
- Otherwise (no answer, or `RETRY`; `mergeCommand`): `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_actions.py merge-command <slug> <dir>` prints
  `{"ok": true, "command": ...}` (the project's `mergeCommand` filled with the url of `mr.md`). If it
  refuses, run `factory_actions.py block <slug> <dir> merge-missing "<its refusal>"`. Otherwise run that
  `command` verbatim with the **Bash tool and `run_in_background`**, and wait for its completion
  notification (do not poll). Exit 0: `factory_actions.py merged <slug> <dir>`. Non-zero:
  `factory_actions.py block <slug> <dir> merge-missing "<short stderr>"`.

### Self-recording an MR or a merge the session already holds

Before printing the `answer` hint for `mr-missing` or `merge-missing`, check whether this session already holds the answer:

- (a) The merge request you opened in this session for `<slug>` from `<directory>` (for example through a project skill on the human's
  request) and whose URL a tool call showed: record it with
  `factory_actions.py answer <slug> <dir> "<url> (recorded by the orchestrator: <tool and URL>)"` and continue the loop.
  When in doubt that the merge request is this job's, print the hint.
- (b) The human asked in this conversation to merge this merge request:
  - When `next` offers `RETRY` (`mergeCommand` or `mergeSkill` is configured), record
    `factory_actions.py answer <slug> <dir> "RETRY (recorded by the orchestrator: the human asked in chat to merge)"` and continue the
    loop: it runs the drift check and the configured merge.
  - Without a configured way, run `capture_change.py <slug> <dir> --check-drift` first; on drift, re-run state with `--record` and
    continue the loop (review) instead of merging. Only without drift may you merge on the chat request, verify with a tool that it is
    merged, and record `factory_actions.py answer <slug> <dir> "MERGED (recorded by the orchestrator: <tool and URL>)"`, then continue.
  - Outside these steps the orchestrator never merges.

Print the hint only when none of this holds. Record only what the human said in this conversation or what a tool call in this session
showed; never infer one.

## `rework <slug> <note>`

1. Run `factory_actions.py rework <slug> <dir> "<note>"`. It is allowed at `needs-decision` after round 1 (it writes
   `review/round-2/review-human.md`) and while the decision is a current APPROVE and not merged: `stage` `needs-mr`,
   `needs-merge`, or `needs-human` with reason `mr-missing`, `merge-missing` or `manual-verification` (it writes
   `review/round-<N+1>/review-human.md` and a `rework` entry in `answers.md`, which grants the round beyond the cap).
   Otherwise it refuses; **stop** and say why (for example open findings go through the normal loop).
2. Run `factory_state.py <slug> <dir> --record` (`needs-rework`) and continue the loop.

## `revise <slug> <note>`

1. Read `<job_dir>/intent.md` (goal, scope, acceptance criteria). The target is `intent` when the note changes a goal, a scope item
   or an acceptance criterion; otherwise `spec`.
2. Stop any argani agent you are running for this task, then run `factory_actions.py revise <slug> <dir> <target> "<note>"`. It
   archives the documents into `revisions/<n>/` (pending answers included: the human may be asked again) and records the note; if it
   refuses, **stop** and show why.
3. Run `factory_state.py <slug> <dir> --record` (`needs-intake` or `needs-spec`, `reason` `revision`) and continue the loop.
4. The merge request description of an open `mr.md` is refreshed in the Merge section, after the new APPROVE.
