# The argani loop

Reference for the `argani` plugin. It is neutral to project type (applications, documentation,
knowledge bases) and to organization.

## Thesis

Writing the work is no longer the bottleneck. The bottleneck moved to the stages around it:
deciding what is wanted, designing, reviewing, testing, releasing. Those stages run at human
speed and mostly inside conversations, which leave no audit trail. The plugin turns each stage
into a committed artifact, so that who asked for what, what an agent produced, and who approved
it are all readable from the repository.

The loop is one and the same in every mode:

```
intent -> spec -> plan -> work on a branch -> review -> merge request -> operate -> new intent
```

Each stage ends with an artifact; the next stage reads only that artifact.

## Stages

| Stage    | Artifact                                        | Produced by                                 | Human gate                                                                      |
|----------|-------------------------------------------------|---------------------------------------------|---------------------------------------------------------------------------------|
| Intent   | `intent.md`                                     | `/argani:intent` (interview with the human) | Human approves the intent                                                       |
| Spec     | `spec.md`                                       | `/argani:spec` or the spec-writer agent     | Human reviews and approves the spec                                             |
| Plan     | `plan.md`                                       | `/argani:plan` or the builder agent         | Manual mode: human approves before any change. Factory mode: reviewed in the MR |
| Work     | code or documents on the job branch, `build.md` | Human or builder agent                      | none                                                                            |
| Review   | `review/round-N/review-<checklist>.md`          | Reviewer agents                             | none                                                                            |
| Decision | `decision.md`                                   | Approver agent                              | Its output is a merge request, never a merge                                    |
| Operate  | follow-up intents                               | Human, from what production shows           | Human opens the next intent                                                     |

Operate is recorded as a stage but not yet automated.

## Artifact location

Per job, in `<artifactRoot>/<slug>/` (default `argani/<slug>/`, see `config.md`):

```
intent.md     Status: draft | approved by <name> on <YYYY-MM-DD>; acceptance criteria in a fixed shape
spec.md       same Status forms; maps each AC to how it is verified; flags concerns
plan.md       same Status forms; files that change, order, risks, proof
build.md      work done, literal verification output, deviations; ends with === END OF BUILD ===
review/round-N/review-<checklist>.md   line 1 is PASS or CHANGES; ends with === END OF REVIEW ===
decision.md   line 1 is APPROVE or ESCALATE; ends with === END OF DECISION ===
mr.md         merge request URL and branch, written once the MR exists
```

Acceptance criteria use one shape, checked by `scripts/artifact_check.py`:

```
- AC-1: <claim> — verify: <command | test | named manual step>
```

A filler instead of a verification (`TBD`, `TODO`, `N/A`, `none`, `?`, `-`, `...`) or an empty
code span fails the check, so the intent cannot be approved until each AC names a real one.

A criterion that only a human can check (a judgement, or data that never leaves someone's machine)
reads `verify: manual: <who does what>`, and the step must be named (`manual: TBD` fails). Agents
never claim it: the builder lists it under `## Pending human verification` in `build.md` with what
it prepared, the compliance reviewer checks that list instead of evidence, and the approver does not
escalate because of it but copies it into `decision.md` as `## Human verification before merge`.
The merge request carries that list, and the human ticks it before merging.

Artifact prose follows the language of the repository's `CLAUDE.md` or of the user. File names,
Status lines, `AC-n`, `verify:` and verdict words stay in English. So do the `# Intent:`,
`# Spec:` and `# Plan:` title prefixes and the `##` section headings; only the prose is in the
project language.

## Always-on rules

1. Skills advise, hooks enforce. Anything that must always hold is a hook reading the repo config.
2. Nobody approves their own work. The approver's output is a merge request for a human; agents
   never merge or push to a protected branch.
3. Context comes from files, not conversation. Every agent is told which paths to read.
4. One writer per file. Each agent writes only its own artifact.
5. Acceptance criteria must be verifiable. Intent without a command, test, or named manual step
   (`manual: <step>`) per criterion cannot be approved. Manual steps are done by a human before
   merging, never claimed by an agent.
6. The verdict is the first line of a review (`PASS` or `CHANGES`) or decision (`APPROVE` or `ESCALATE`).
7. At most two review rounds, then escalate to a human.
8. A correction made twice becomes a rule in the repo's `CLAUDE.md` or a hook.

## Two modes

**Manual.** A person calls the skills one at a time and performs each gate in place:
`/argani:intent`, approve, `/argani:spec`, approve, `/argani:plan`, approve, then does or directs the work.

**Factory.** `/argani:factory` turns the session into an orchestrator that runs spec, build, review
and decision with fresh subagents, each reading and writing files. It stops at only three
places: the intent (human approves), the spec (human approves), and the merge request (human
reviews and merges). `plan.md` is written by the builder before it changes any code and is
reviewed together with the diff in the merge request. Factory mode is expensive (several agents
per job, up to two rounds), so use it only for jobs with clear acceptance criteria.
The orchestrator is `skills/factory/SKILL.md`; it re-reads job state each time from
`scripts/factory_state.py <slug>`, which only reports and never writes.

Who commits what on the job branch: the builder commits code, `plan.md` and `build.md`; the
orchestrator commits the rest of the job folder (`intent.md`, `spec.md`, `review/**`, `decision.md`,
`mr.md`), adding only paths under `<artifactRoot>/<slug>/`: before the build, after each review round,
after the decision and before the push. Nothing is ever pushed or merged without a human.
Running `/argani:factory` is the explicit instruction for exactly these commits; a repository that
requires a separate instruction for every commit uses the manual loop instead. Commit subjects and
trailers follow `recordCommitMessage` and `commitTrailers` in `.claude/argani.json`.

## Reviewers

There is one generic reviewer agent. What it checks comes from a checklist in the catalog
(`code`, `security`, `compliance`, `ux`, `ui-design`, `citation`, `format`). The repository
chooses the active checklists through `reviewers` in `.claude/argani.json`.

## Adoption order

1. Intent, spec and plan skills; usable immediately, by hand.
2. Review protocol and enforcing hooks.
3. Generic agents and the checklist catalog.
4. Factory orchestrator ending in a merge request.
5. Eval suite, then bootstrap of global configuration.

## Verified behaviour

Facts observed by running the plugin (Claude Code 2.1.310), not read from documentation.

- **Agent names.** The Agent tool accepts only the plugin-prefixed form: `subagent_type: "argani:<agent>"`
  (e.g. `argani:reviewer`). The bare name is rejected. Scope tools as `Agent(argani:reviewer)`.
- **Hooks inside subagents.** Plugin `PreToolUse` hooks fire for tool calls made inside a subagent.
  Their stdin JSON then also carries `agent_id` and `agent_type`, with `agent_type` exactly
  `argani:<agent>`. The main session has neither key. `cwd` is the directory the session was launched
  in, so the repository is resolved with `git -C <cwd> rev-parse --show-toplevel`.
- **Hook stdin fields.** `session_id, transcript_path, cwd, permission_mode, hook_event_name,
  tool_name, tool_input, tool_use_id`. Bash `tool_input`: `command, description`; Write:
  `file_path, content`; Edit: `file_path, old_string, new_string, replace_all`.
- **Eval graders.** `file_exists` accepts globs and `exists: false` for "must not exist". A `regex`
  grader on a missing file fails (reported as "grader threw"); it does not crash the run, so assert
  absence with `file_exists`, never with `regex`.
- **Eval cases.** Quote the version: `schema_version: "1.0"`. A case that writes files needs
  `allowed_tools` in `prompt.md` and the run needs `--allow-tools Write Bash`; headless runs need
  `--trust-plugin`; add `--ablation none` to skip the no-plugin baseline arm.
- **Scoped Bash in agent `tools` is not enforced.** An agent declared with
  `tools: ..., Bash(git diff *), Bash(git log *)` (the reviewer) ran `git status` successfully,
  with and without `Bash` in the parent's `--allowedTools`; the agent reported its tools as
  `Read, Glob, Grep, Write, Bash`. The `Bash(git diff:*)` spelling behaves the same. The scoped
  entries only make `Bash` available; they are not a command allowlist, so treat the narrow scope
  as documentation of intent. The restriction is enforced by `guard_git.py` (per-agent Bash
  allowlist, see `review-protocol.md`).
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
  null device, so any git call fails with `Permission denied` even though `Bash` is granted with
  `--allow-tools`; the grant is not the cause and no flag restores it. Evals whose subject needs
  git (`/argani:review`, the factory) cannot pass by design, so they are not evals; they are covered by
  pytest and a manual headless smoke (see `evals/README.md`).
