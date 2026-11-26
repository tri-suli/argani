# The argani loop

Reference for the `argani` plugin. It is neutral to project type (applications, documentation,
knowledge bases) and to organization.

## Thesis

Writing the work is no longer the bottleneck. The bottleneck moved to the stages around it:
deciding what is wanted, designing, reviewing, testing, releasing. Those stages run at human
speed and mostly inside conversations, which leave no audit trail. The plugin turns each stage
into a written artifact, so that who asked for what, what an agent produced, and who approved it
are all readable afterwards: in the task folder of the argani home (a plain folder).

The loop is one and the same in every mode:

```
intent -> spec -> plan -> work -> review -> merge request -> operate -> new intent
```

Each stage ends with an artifact; the next stage reads only that artifact.

## Stages

| Stage    | Artifact                                        | Produced by                                 | Human gate                                                                      |
|----------|-------------------------------------------------|---------------------------------------------|---------------------------------------------------------------------------------|
| Intent   | `intent.md`                                     | `/argani:intent` (interview with the human) or the intake agent | Manual mode: human approves. Factory mode: the orchestrator approves; a human only answers `## Questions for human` |
| Spec     | `spec.md`                                       | `/argani:spec` or the spec-writer agent     | Manual mode: human approves. Factory mode: the orchestrator approves; a human only answers `## Questions for human` |
| Plan     | `plan.md`                                       | `/argani:plan` or the builder agent         | Manual mode: human approves before any change. Factory mode: reviewed in the MR |
| Work     | code or documents in the project, `build.md`    | Human or builder agent                      | none                                                                            |
| Review   | `review/round-N/change.diff`, `review/round-N/review-<checklist>.md` | `capture_change.py` (the change), reviewer agents | none                                                                            |
| Decision | `decision.md`                                   | Approver agent                              | Its output is a merge request, never a merge by the approver; the project's `mergeCommand` merges it (Needs human only when it is missing or fails); the MR description is generated from the intent and the decision; its title is the intent heading, or the output of `mrTitleCommand` |
| Operate  | follow-up intents                               | Human, from what production shows           | Human opens the next intent                                                     |

Operate is recorded as a stage but not yet automated.

## Artifact location

Per job, in the task folder `<home>/projects/<project>/tasks/<slug>/` of the argani home (nothing is
written into the project directory). An optional `Risk:` line in `intent.md` (`low`, `medium` or
`high`, default `medium`) picks the models of the agents through `agentModels`.

```
intent.md     Status: draft | approved by <name> on <YYYY-MM-DD>; acceptance criteria in a fixed shape
spec.md       same Status forms; maps each AC to how it is verified; flags concerns
plan.md       same Status forms; files that change, order, risks, proof
build.md      work done, literal verification output, deviations; ends with === END OF BUILD ===
review/round-N/change.diff              the change under review, captured by capture_change.py before the round
review/round-N/review-<checklist>.md   line 1 is PASS or CHANGES; ends with === END OF REVIEW ===
decision.md   line 1 is APPROVE or ESCALATE; ends with === END OF DECISION ===
mr-body.md    merge request description generated from intent.md and decision.md (acceptance criteria, human checklist, task folder)
mr.md         merge request URL, written once the MR exists; `Merged: <YYYY-MM-DD>` is appended once it is merged (by the orchestrator after `mergeCommand`, or by the human in manual mode)
answers.md    the human's answers, `## <reason> <question-id> <YYYY-MM-DD>` plus the reply; written by the orchestrator (`/argani:factory answer`)
blocked.md    line 1 `<reason> <id>` (`agent-failed`, `mr-missing`, `merge-missing`), then a summary; written by the orchestrator when a seat or command fails
history.jsonl one line per change of (stage, column, reason); appended by `factory_state.py --record`, `factory_actions.py` and `board.py --write`
```

Acceptance criteria use one shape, checked by `scripts/artifact_check.py`:

```
1. [ ] <claim> — verify: <command | test | named manual step>
2. [ ] <claim> — verify: manual: <who does what>
```

Items are numbered 1 to n in order; item n is AC-n wherever it is referred to (the spec's mapping
table, `build.md`, reviews, `decision.md`, and in conversation). The checkbox may be ticked
(`[x]`) without changing anything. The old `- AC-n: ...` bullets fail the check.

A filler instead of a verification (`TBD`, `TODO`, `N/A`, `none`, `?`, `-`, `...`) or an empty
code span fails the check, so the intent cannot be approved until each AC names a real one.

A criterion that only a human can check (a judgement, or data that never leaves someone's machine)
reads `verify: manual: <who does what>`, and the step must be named (`manual: TBD` fails). Agents
never claim it: the builder lists it under `## Pending human verification` in `build.md` with what
it prepared, the compliance reviewer checks that list instead of evidence, and the approver does not
escalate because of it but copies it into `decision.md` as `## Human verification before merge`.
The merge request carries that list, and the human ticks it before merging.

Artifact prose follows the language of the project's `CLAUDE.md` or of the user. File names,
Status lines, `AC-n`, `verify:` and verdict words stay in English. So do the `# Intent:`,
`# Spec:` and `# Plan:` title prefixes and the `##` section headings; only the prose is in the
project language.

## Board

`scripts/board.py` lists every task of the registered projects by column. The column derives from the stage and from whether a human answer is waiting to be acted on (`scripts/board_columns.py`); nothing else is stored separately. Columns, in order: Intake, Spec, Build, Review, Approve, Needs human, Done.

| Stage | Column |
|---|---|
| `needs-intake`, `needs-intent-approval` | Intake |
| `needs-spec`, `needs-spec-approval` | Spec |
| `needs-build`, `needs-rework` | Build |
| `needs-review` | Review |
| `needs-decision`, `needs-mr`, `needs-merge`; any other stage with an answer not yet acted on | Approve |
| `needs-human`, `error` (the task cannot be read: broken config, unreadable file) | Needs human |
| `done`, `cancelled` | Done |

```
python3 board.py [dir]                    # the project of dir (default: the current directory)
python3 board.py --all [--write] [--json] # every project; --write saves <home>/board.md and <home>/board.json
```

`/argani:board [--all]` runs `board.py` and shows the result.

`board.md` and `board.json` are generated and never edited by hand; they are regenerated on every `--write`. `--write` first appends the current `(stage, column, reason)` of every non-error task to its `history.jsonl` (skipped when unchanged); without `--write` nothing is written. In `board.md` a Needs human task shows `question: <question>` instead of `next:`.

### board.json

A read-only snapshot for user interfaces; `--json` prints the same object. Top-level keys: `home`,
`generatedAt` (UTC, `YYYY-MM-DDTHH:MM:SSZ`), `columns` (the column order), `projects[]` and `agents[]`.
Each project is `{name, tasks[]}`; each task has `project`, `slug`, `title`, `stage`, `column`, `merged`,
`next`, `reason` (why the task waits for a human, else null), `question` (the question for the human, else null),
`history[]` (the valid entries of `history.jsonl`: `ts`, `stage`, `column`, `reason`), `durations[]`
(`{column, milliseconds}` per history entry, the last running until generation) and `metrics`
(`manualAcceptanceCriteria`, `needsHumanCount`, `needsHumanMilliseconds`). An error task has stage `error`,
column Needs human, reason `error`, the error message as `question`, and empty history and durations. `agents[]` holds the active argani agents: the `spawn` records of the [Event log](#event-log)
(fields there, unchanged), so a UI joins them to tasks on `project` + `slug`. An agent is active when its
`spawn` has no `finish` with the same `tool_use_id` in the event files of today and yesterday (local
dates), in file order; a `spawn` without a string `tool_use_id` is never active. The window is the only
expiry: a `spawn` that never got a `finish` (the session died, the Agent call was denied, blocked by
another hook or interrupted) stays listed until its file ages out, and an agent still running when its
file ages out disappears early. A background agent reports `finish` with `status: async_launched`
at launch, so it would be dropped early; argani's skills do not use them. `agents` ignores the project
filter: it always lists every active agent of the home. An unreadable event file or malformed line is
skipped with a warning on stderr.

A project whose `project.json` is unreadable is skipped with a warning on stderr and is absent from the board.

Done is decided by `mr.md` alone: when the merge request is merged, the human appends a line
`Merged: <YYYY-MM-DD>` (a valid date at the start of a line); in factory mode the orchestrator appends it after `mergeCommand` exits 0. argani never looks at branches or
remotes, so a merge by any means (squash, rebase, a deleted branch) is recognised the same way.

After APPROVE the job's scope is closed: the approver judged the change against `spec.md` and the
acceptance criteria of `intent.md`, and the merge request carries that judgement. Work that grows
beyond the approved spec while the merge request is open is a new intent, not an edit of this
job: a long-lived merge request that keeps absorbing scope leaves `mr-body.md`, the acceptance
criteria and the human checklist stale, and nothing in argani re-reviews it. argani does not
amend an approved spec; `mr_description.py` only warns when `intent.md` changed after
`decision.md`.

## Always-on rules

1. Skills advise, hooks enforce. Anything that must always hold is a hook reading the project config.
2. Nobody approves their own work. The approver's output is a merge request; it is merged by the
   project's `mergeCommand` (or by a human), never by argani's own code. Intake and spec-writer write
   drafts; the orchestrator, not their author, writes the approval.
3. Context comes from files, not conversation. Every agent is told which paths to read.
4. One writer per file. Each agent writes only its own artifact; `change.diff` is written by
   `capture_change.py` alone (Write and Edit of it are denied to everyone).
5. Acceptance criteria must be verifiable. Intent without a command, test, or named manual step
   (`manual: <step>`) per criterion cannot be approved. Manual steps are done by a human before
   merging, never claimed by an agent.
6. The verdict is the first line of a review (`PASS` or `CHANGES`) or decision (`APPROVE` or `ESCALATE`).
7. At most two review rounds; a third needs a recorded human answer, otherwise the task waits as Needs human.
8. A correction made twice becomes a rule in the project's `CLAUDE.md` or a hook.

## What argani does not do

argani never runs git and has no opinion about it. Branches, worktrees, commits, pushes and merges
(and their names, trailers and protection) are the project's, done with the project's own rules and
skills. argani creates and switches no branch, makes no worktree, commits and pushes nothing, merges
only by running the project's `mergeCommand`, guards no git command, names no branch and reads no remote. What it needs from the project is two
commands in `project.json`: `verifyCommand` (proves the work) and `diffCommand` (prints the change
under review). Before `/argani:factory` the human, or the project's own skills, prepare the branch or
worktree and either start the session in that directory or pass it as `in <dir>` (the working
directory; the agents run every command from it). A working directory nested inside the registered path
(for example `.worktrees/<slug>`) must be covered by a `paths` pattern in `project.json`
(`docs/config.md`), otherwise the project root is the outer checkout and `diffCommand` and
`protectedPaths` use the wrong root. The agents follow the project's
own protocols: the rules Claude Code loaded plus the working directory's `CLAUDE.md`, its `@<path>`
imports and `.claude/rules/**/*.md` (the working directory's copy wins over the session directory's).
A protocol wins over argani on how the work is done, never over the artifact protocol. A project skill
the builder invokes runs its commands from the working directory, like every other command (only a
skill with `context: fork` cannot be redirected). The builder prompt carries an `Instruction` line
saying the human ran `/argani:factory`; it counts as explicit instruction only for steps the
protocols assign to the builder (such as its own commit), never for a push, a merge or branches.

## Two modes

**Manual.** A human at every step: a person calls the skills one at a time and performs each gate in place:
`/argani:intent`, approve, `/argani:spec`, approve, `/argani:plan`, approve, then does or directs the
work and calls `/argani:review`.

**Factory.** `/argani:factory "<description>"` turns the session into an orchestrator that runs the whole
loop autonomously: intake (the intake agent writes `intent.md` from the description and the repository),
spec, build, review and decision with fresh subagents, each reading and writing files, then the merge
request (`mrCommand`) and the merge (`mergeCommand`). The orchestrator writes the intent and spec
approvals itself (through `scripts/factory_actions.py`). It stops only when a human must answer a
specific question: `## Questions for human` in the intent or spec, manual verification steps, an
escalation, a missing or failed `mrCommand` / `mergeCommand`, or an agent that failed twice. The human
answers with `/argani:factory answer <slug> <answer>`; the answer is recorded in `answers.md` and the
loop continues. `plan.md` is written by the builder before it changes any code and is reviewed together
with the change in the merge request. Factory mode is expensive (several agents per job, up to two rounds
without a human answer), so use it only for jobs with clear acceptance criteria.
The orchestrator is `skills/factory/SKILL.md`; it re-reads job state each time from
`scripts/factory_state.py <slug> <dir> --record`, which only reports (and appends the stage to the history).

Before each review round the orchestrator runs `scripts/capture_change.py <slug> <dir>`: it runs the
project's `diffCommand` with the project root of the working directory as working directory and saves the output as
`review/round-<N>/change.diff`; once a reviewer has worked on a round its change is fixed and is not
captured again. Reviewers and the approver read that file; they have no shell. The
files named in it also decide which checklists run when `reviewerPaths` is set. If `diffCommand`
prints nothing there is nothing to review and the factory stops.

## Reviewers

There is one generic reviewer agent. What it checks comes from a checklist in the catalog
(`code`, `security`, `compliance`, `ux`, `ui-design`, `citation`, `format`). The project
chooses the active checklists through `reviewers` in its `project.json`.

## Adoption order

1. Intent, spec and plan skills; usable immediately, by hand.
2. Review protocol and enforcing hooks.
3. Generic agents and the checklist catalog.
4. Factory orchestrator ending in a merge request.
5. Eval suite.

## Moving legacy jobs

A project that kept its jobs in `<artifactRoot>/<slug>/` before 1.0.0 and is now registered moves
them with `/argani:import [<slug> ...]`. It reads the working tree only (a job that lives only on a
branch has to be checked out first, with the project's own tools) and copies the files to
`<home>/projects/<project>/tasks/<slug>/` after the human confirms. Each written file is compared
with the bytes read from the source. Symbolic links are never followed or copied. A destination
that holds exactly the found files is `already-imported` (a rerun is safe); one with different or
extra files is a conflict and is never written. The project is not modified and nothing is deleted;
removing the old folders and `.claude/argani.json` goes through the project's own process.

## Event log

`hooks/log_events.py` appends one JSON line per event to `<home>/events/<YYYY-MM-DD>.jsonl` (the local date;
the folder is created on the first event, and nothing is written when the home does not exist). The
log is append-only; `board.py` reads it for the active agents of `board.json`. Only `argani:*` agents are logged. Every line has `ts`
(UTC), `event`, `session_id` and `agent_type`, plus the fields below. For `spawn` and `finish` the `agent_type` is the agent that was
called and `parent_agent_type` the one that called it (`null` in the main session).

| Event | When | Fields |
|---|---|---|
| `spawn` | `PreToolUse` of the Agent tool | `tool_use_id`, `model` (when given), `project`, `slug` (from the prompt's `Slug folder:` or `Intent:` path, else `null`), `parent_agent_type`, `cwd` |
| `start` | `SubagentStart` | `agent_id` |
| `stop` | `SubagentStop` | `agent_id`, `agent_transcript_path`, `last_assistant_message` (first 500 characters) |
| `finish` | `PostToolUse` of the Agent tool | `tool_use_id`, `agent_id`, `status`, `parent_agent_type`, `duration_ms`, `project`, `slug`, `usage` (the four token counts: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`) and `totalTokens` when present |

Correlation: `spawn` and `finish` share `tool_use_id`; `start`, `stop` and `finish` share `agent_id`.
`status` of `finish` tells a launch from a completion: an agent started in the background reports `async_launched` when it is launched, so `stop` is the real end of a background agent (argani's skills do not launch agents in the background today). `ts` is UTC while the file name is the local date, so the events of one agent can straddle midnight.

## Verified behaviour

Facts observed by running the plugin (Claude Code 2.1.310), not read from documentation.

- **Agent names.** The Agent tool accepts only the plugin-prefixed form: `subagent_type: "argani:<agent>"`
  (e.g. `argani:reviewer`). The bare name is rejected. Scope tools as `Agent(argani:reviewer)`.
- **Hooks inside subagents.** Plugin `PreToolUse` hooks fire for tool calls made inside a subagent.
  Their stdin JSON then also carries `agent_id` and `agent_type`, with `agent_type` exactly
  `argani:<agent>`. The main session has neither key. `cwd` is the directory the session was launched
  in, so the project is resolved from the real path of `cwd`.
- **Hook stdin fields.** `session_id, transcript_path, cwd, permission_mode, hook_event_name,
  tool_name, tool_input, tool_use_id`. Bash `tool_input`: `command, description`; Write:
  `file_path, content`; Edit: `file_path, old_string, new_string, replace_all`.
- **Eval graders.** `file_exists` accepts globs and `exists: false` for "must not exist". A `regex`
  grader on a missing file fails (reported as "grader threw"); it does not crash the run, so assert
  absence with `file_exists`, never with `regex`.
- **Eval cases.** Quote the version: `schema_version: "1.0"`. A case that writes files needs
  `allowed_tools` in `prompt.md` and the run needs `--allow-tools Write Bash`; headless runs need
  `--trust-plugin`; add `--ablation none` to skip the no-plugin baseline arm.
- **Scoped Bash in agent `tools` is not enforced.** An agent declared with a scoped entry such as
  `Bash(git diff *)` ran other commands successfully, with and without `Bash` in the parent's
  `--allowedTools`; the scoped entries only make `Bash` available, they are not a command allowlist.
  That is why the reviewer and the approver have no `Bash` at all (tools `Read, Glob, Grep, Write`):
  they read `change.diff` instead of running anything.
- **`${CLAUDE_PLUGIN_ROOT}` in agent frontmatter.** A spec-writer declared with
  `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)` was spawned with the installed plugin path in its
  prompt, wrote a spec that `artifact_check.py spec` accepted, and ran that script. Because scoped
  Bash is not enforced (above), this does not prove the variable expands inside `tools`; agent
  bodies therefore use the `Plugin root` given in the prompt, never the variable.
- **Eval scaffolds and judges.** `case.yaml` `context.scaffold_script` is a path (relative to the
  case folder) to a bash script, not inline text, and it only runs with `--scaffold`. An `llm`
  grader takes `criteria` from its body and `focus` (default `last_message`); to judge a file use
  `focus: {source: file, path: ...}`. It has no `target` key (that is `regex` only).
- **No git in the eval sandbox.** Inside `claude plugin eval` runs `/usr/bin/git` is replaced by the
  null device. argani needs none since 2.0.0: a project is found by its registered path, so the
  eval scaffold registers a plain directory. A `diffCommand` for an eval project must not use git.
