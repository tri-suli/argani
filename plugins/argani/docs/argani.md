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
| Intent   | `intent.md`                                     | `/argani:intent` (interview with the human) | Human approves the intent                                                       |
| Spec     | `spec.md`                                       | `/argani:spec` or the spec-writer agent     | Human reviews and approves the spec                                             |
| Plan     | `plan.md`                                       | `/argani:plan` or the builder agent         | Manual mode: human approves before any change. Factory mode: reviewed in the MR |
| Work     | code or documents in the project, `build.md`    | Human or builder agent                      | none                                                                            |
| Review   | `review/round-N/change.diff`, `review/round-N/review-<checklist>.md` | `capture_change.py` (the change), reviewer agents | none                                                                            |
| Decision | `decision.md`                                   | Approver agent                              | Its output is a merge request, never a merge by the approver; the MR description is generated from the intent and the decision |
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
mr.md         merge request URL, written once the MR exists; the human appends `Merged: <YYYY-MM-DD>` once it is merged
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

`scripts/board.py` lists every task of the registered projects by column. The column derives from the stage; nothing is stored separately.

| Stage | Column |
|---|---|
| `needs-intent-approval` | Backlog |
| `needs-spec`, `needs-spec-approval` | Design |
| `needs-build`, `needs-rework`, `needs-review`, `needs-decision` | In progress |
| `needs-mr` | Ready for MR |
| `done`, `mr.md` without a valid `Merged: <date>` line | In review |
| `done`, `mr.md` has a valid `Merged: <YYYY-MM-DD>` line | Done |
| `escalate` | Needs human |
| `error` (the task cannot be read: broken config, unreadable file) | Needs human |

```
python3 board.py [dir]                    # the project of dir (default: the current directory)
python3 board.py --all [--write] [--json] # every project; --write saves <home>/board.md
```

`/argani:board [--all]` runs `board.py` and shows the result.

`board.md` is generated and never edited by hand; it is regenerated on every `--write`.

A project whose `project.json` is unreadable is skipped with a warning on stderr and is absent from the board.

Done is decided by `mr.md` alone: when the merge request is merged, the human appends a line
`Merged: <YYYY-MM-DD>` (a valid date at the start of a line). argani never looks at branches or
remotes, so a merge by any means (squash, rebase, a deleted branch) is recognised the same way.

## Always-on rules

1. Skills advise, hooks enforce. Anything that must always hold is a hook reading the project config.
2. Nobody approves their own work. The approver's output is a merge request for a human; merging is
   the human's and the project's own business, never argani's.
3. Context comes from files, not conversation. Every agent is told which paths to read.
4. One writer per file. Each agent writes only its own artifact; `change.diff` is written by
   `capture_change.py` alone (Write and Edit of it are denied to everyone).
5. Acceptance criteria must be verifiable. Intent without a command, test, or named manual step
   (`manual: <step>`) per criterion cannot be approved. Manual steps are done by a human before
   merging, never claimed by an agent.
6. The verdict is the first line of a review (`PASS` or `CHANGES`) or decision (`APPROVE` or `ESCALATE`).
7. At most two review rounds, then escalate to a human.
8. A correction made twice becomes a rule in the project's `CLAUDE.md` or a hook.

## What argani does not do

argani never runs git and has no opinion about it. Branches, worktrees, commits, pushes and merges
(and their names, trailers and protection) are the project's, done with the project's own rules and
skills. argani creates and switches no branch, makes no worktree, commits, pushes and merges nothing,
guards no git command, names no branch and reads no remote. What it needs from the project is two
commands in `project.json`: `verifyCommand` (proves the work) and `diffCommand` (prints the change
under review). Before `/argani:factory` the human, or the project's own skills, prepare the branch or
worktree and either start the session in that directory or pass it as `in <dir>` (the working
directory; a project skill the builder invokes runs from the session directory unless it takes
the directory as an argument, so starting the session there is simpler). A working directory nested inside the registered path
(for example `.worktrees/<slug>`) must be covered by a `paths` pattern in `project.json`
(`docs/config.md`), otherwise the project root is the outer checkout and `diffCommand` and
`protectedPaths` use the wrong root. The builder follows the
project's `CLAUDE.md` for
commits.

## Two modes

**Manual.** A person calls the skills one at a time and performs each gate in place:
`/argani:intent`, approve, `/argani:spec`, approve, `/argani:plan`, approve, then does or directs the
work and calls `/argani:review`.

**Factory.** `/argani:factory` turns the session into an orchestrator that runs spec, build, review
and decision with fresh subagents, each reading and writing files. It stops at only three
places: the intent (human approves), the spec (human approves), and the merge request (human
reviews and merges). `plan.md` is written by the builder before it changes any code and is
reviewed together with the change in the merge request. Factory mode is expensive (several agents
per job, up to two rounds), so use it only for jobs with clear acceptance criteria.
The orchestrator is `skills/factory/SKILL.md`; it re-reads job state each time from
`scripts/factory_state.py <slug> <dir>`, which only reports and never writes.

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
