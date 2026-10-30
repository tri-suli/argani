# Review protocol

How reviews and decisions are written, counted and enforced. `hooks/guard_artifacts.py` enforces
the mechanical parts (verdict line, round limit, who writes what); the rest is instruction.

## Files

All paths are under the task folder `<home>/projects/<name>/tasks/<slug>/` in the argani home.

| File                                   | Written by                                          | Line 1                  | Last line                 |
|----------------------------------------|-----------------------------------------------------|-------------------------|---------------------------|
| `review/round-N/change.diff`           | `capture_change.py` (run by the main session)       | a unified diff          | none                      |
| `review/round-N/review-<checklist>.md` | `argani:reviewer`, one per checklist in `reviewers` | `PASS` or `CHANGES`     | `=== END OF REVIEW ===`   |
| `review/round-N/review-human.md`       | the orchestrator or human, from a `rework` note     | `CHANGES`               | `=== END OF REVIEW ===`   |
| `decision.md`                          | `argani:approver`                                   | `APPROVE` or `ESCALATE` | `=== END OF DECISION ===` |

`<checklist>` is a name from `checklists/` (`code`, `security`, `compliance`, `ux`, `ui-design`, `citation`, `format`).
`N` starts at 1. `change.diff` is the change under review in round `N`: the output of the project's
`diffCommand`, captured before the reviewers are spawned. It is never written by an agent; reviewers
and the approver only read it.

## Verdict line

Line 1 is exactly the verdict word, optionally followed by one space and a short reason:

```
CHANGES missing test for the empty-input case
```

Nothing may precede it: no heading, no blank line, no prefix such as `Result:`. The hook matches
`^(PASS|CHANGES)(\s|$)` (review) and `^(APPROVE|ESCALATE)(\s|$)` (decision) and denies the write
otherwise, telling the agent the expected first line.

`PASS` means no Important finding. `CHANGES` means at least one Important finding. Nits alone
never justify `CHANGES`.

## Findings

Below the verdict, one finding per bullet:

```
- [Important] src/auth.py:42 - What: token compared with `==`. Why: timing side channel. Fix: use hmac.compare_digest.
- [Nit] README.md:7 - What: typo "recieve". Why: reads as careless. Fix: "receive".
```

- Severity is `Important` or `Nit`. Important blocks the merge request; a Nit does not.
- Location is `file:line` (or `file:start-end`). A finding about a missing file names the expected path.
- Every finding states what is wrong, why it matters, and the fix.
- At most 5 nits per file. Beyond five, keep the five that matter most and say how many were dropped.
- Findings outside the checklist's scope are not reported (each checklist lists what to skip).

## Closing line

The last line of every review and decision is the literal closing line from the table above. A file
without it is treated as cut off: the seat is rerun, and the partial file is overwritten.

## Rounds and "wait for all"

- A round is **complete** only when every checklist the job needs has a file in
  `review/round-N/` that ends with the closing line. The job needs every checklist in `reviewers`,
  except one scoped by `reviewerPaths` whose paths the round's `change.diff` does not touch;
  `factory_state.py` reports the list as `reviewers`. Do not summarise, decide, or start rework
  on a partial round.
- `review-human.md` is extra: it does not count toward completeness and does not replace a seat.
- If any file in a complete round says `CHANGES`, the builder reworks and a new round `N+1` starts.
  All files are read; one `PASS` never cancels another file's `CHANGES`.
- All files `PASS` means the approver is spawned and writes `decision.md`.
- **Two rounds at most.** The hook refuses any write under `review/round-3/` or higher
  (`N >= 3`). If round 2 still has `CHANGES`, stop and escalate to a human; do not try to work
  around the refusal.
- The approver judges only the seats in `reviewers`. A `review-human.md` counts as addressed once
  `build.md` has the heading `## Rework after round <N>` for the current round `N`, and then does not
  by itself cause `ESCALATE`; without that heading it does. The builder writes one such heading for
  every round whose files are listed in its `Findings to address`. Any other file in the round folder is reported in
  `decision.md` and ignored for the verdict.
- `human` is reserved: a configured reviewer may not be named `human`.
- `ESCALATE` in `decision.md` stops the job and marks it as needing a human.
- `APPROVE` still ends in a merge request that a human reviews and merges. argani never merges.

## One writer per file

The hook reads `agent_type` from the hook input (value `argani:<agent>`):

| Agent                | May write (in the task folder `<home>/projects/<name>/tasks/<slug>/`) | May not write                                                                               |
|----------------------|-------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| `argani:reviewer`    | `review/round-*/review-*.md`                                      | anything else, in the argani home or in a project directory (`change.diff` included)       |
| `argani:approver`    | `decision.md`                                                     | anything else, in the argani home or in a project directory (`change.diff` included)       |
| `argani:spec-writer` | `spec.md`                                                         | anything else, in the argani home or in a project directory (`change.diff` included)       |
| `argani:builder`     | `plan.md`, `build.md`; source files in the project directory      | in the task folder: `intent.md`, `spec.md`, `review/**` (`change.diff` included), `decision.md`, `mr.md` |

`change.diff` is written by `scripts/capture_change.py` alone, through `Bash`. The guard denies
`Write` and `Edit` of it to **every** caller, the main session included, and to subagents of any
plugin. Writes through `Bash` are not guarded: the builder has full `Bash` and is told not to touch the
task folder except `plan.md` and `build.md`. A round's `change.diff` is fixed once a reviewer has worked
on it: `capture_change.py` refuses to replace it.

In a project directory the guard applies only `protectedPaths` and the one-writer rule: the three
sole writers may write nothing there, and the builder, the main session and other agents are not
restricted beyond `protectedPaths`. Writes in the task folder that pass the rules
are explicitly allowed by the guard, which also spares the permission prompt for writes outside the
working directory. `protectedPaths` apply to the project directory only.

Verified 2026-10-28 with `claude -p --plugin-dir` (headless): a Write to
`<home>/projects/demo/tasks/login/intent.md` succeeded through the guard's allow, while a Write to
another folder outside the working directory was refused. Whether `deny` rules in the user's settings
outrank a hook allow was not tested.

Paths outside any registered project are not touched by this rule for the main session and other
agent types. A reviewer writes only the file for its own checklist; the hook cannot tell which
checklist a reviewer was given, so that part is an instruction in the agent prompt.

## Running a round

**Manual mode.** `/argani:review <slug> [in <dir>]`:
1. Read `reviewers` and `diffCommand` from the project configuration (`argani_config.py`).
2. Run `capture_change.py <slug> <dir>`: it runs `diffCommand` in the project root of the working directory and writes
   `review/round-N/change.diff`. An empty diff stops the round: nothing to review.
3. In one message, spawn one `argani:reviewer` per checklist (parallel). Each prompt names the
   checklist file, the slug folder, the round and the `Change` file; the reviewer writes its one
   output path.
4. Wait until every expected file exists and ends with the closing line; rerun any cut-off seat.
5. Report each verdict. The human decides whether to rework or run the approver.

**Factory mode.** `/argani:factory` runs the same round after the builder finishes, then:
`CHANGES` anywhere starts a new round with a fresh builder that reads the round folder;
all `PASS` spawns the approver; round 3 is refused by the hook and the job escalates.
Agents do not carry memory between steps: every spawn reads files named in its prompt.

**Human rework.** `/argani:factory rework <slug> [in <dir>] <note>` writes `review/round-N+1/review-human.md`
with `CHANGES` on line 1, the note as an Important finding, and the closing line, then continues
as a normal round. It is allowed only after a clean round 1 and before a decision; it is refused
after round 2, and the hook denies `round-3`.

## Version control

Not argani's business. The builder follows the project's own protocols (`CLAUDE.md`, its `@` imports and `.claude/rules/*.md`) and skills for commits;
the task folder is outside the project and is never part of a commit.

## Agents

Agents get context from files only; every spawn prompt names the files to read. Each writes exactly
one artifact. Spawn them with `subagent_type: "argani:<agent>"`.

| Agent                | Reads                                                                        | Writes                                               | Closing line                                                                            |
|----------------------|------------------------------------------------------------------------------|------------------------------------------------------|-----------------------------------------------------------------------------------------|
| `argani:spec-writer` | `intent.md`, project protocols (CLAUDE.md, @imports, .claude/rules), config  | `spec.md`                                            | none (spec stays human-editable; completeness is checked with `artifact_check.py spec`) |
| `argani:builder`     | `spec.md`, `plan.md`, previous round folder, project protocols (CLAUDE.md, @imports, .claude/rules)| code in the project, `plan.md` if missing, `build.md` | `=== END OF BUILD ===`                                                                  |
| `argani:reviewer`    | one checklist, project protocols (CLAUDE.md, @imports, .claude/rules), `spec.md`, `plan.md`, `build.md`, `change.diff`| `review/round-N/review-<checklist>.md`               | `=== END OF REVIEW ===`                                                                 |
| `argani:approver`    | latest round folder, `build.md`, `spec.md`, `plan.md`, `change.diff`         | `decision.md`                                        | `=== END OF DECISION ===`                                                               |

### Spawn prompts

Agents see nothing but the prompt and the files it names. `Plugin root` is the value of
`${CLAUDE_PLUGIN_ROOT}` (agent bodies do not rely on it being expanded). Skeletons:

```
# argani:spec-writer
Plugin root: <plugin root>
Intent: <abs path to intent.md>
Spec: <abs path to spec.md>
Config: <effective config JSON>
Language: <project language>

# argani:builder
Plugin root: <plugin root>
Slug folder: <abs slug folder>
Verify command: <verifyCommand>
Round: <N>
Findings to address:                                 # only when N > 1: one abs path per review file
- <abs review/round-K/review-<checklist>.md>         # of round N-1 (and of round N when it holds
                                                     # review-human.md)

# argani:reviewer
Plugin root: <plugin root>
Checklist: <name>
Checklist file: <plugin root>/checklists/<name>.md
Slug folder: <abs slug folder>
Round: <N>
Change: <abs review/round-N/change.diff>

# argani:approver
Plugin root: <plugin root>
Slug folder: <abs slug folder>
Round folder: <abs review/round-N>
Change: <abs review/round-N/change.diff>
Reviewers: <comma-separated checklist names>
Protected paths: <comma-separated globs, or "none">
```

## Accepted bypasses

The hooks are a guard against mistakes, not a sandbox. These are known and accepted:

- Writing a file through Bash (heredoc, `tee`, `sed -i`) bypasses `guard_artifacts.py`, which only
  sees `Write` and `Edit`. The reviewer and the approver have no `Bash`, but the builder and the
  main session do (so `change.diff` could be rewritten through `Bash`; the builder's instructions
  forbid it).
- A broken project configuration is not a bypass: the artifact guard asks (main session) or denies
  (subagent) for every write inside the project directory, because `protectedPaths` cannot be
  checked.

Acceptable because the reviewer, approver and spec-writer have `Write`, but the hook limits it to
their own file everywhere: any other path is denied, including paths outside the project and under
`.git/`. The harness does not enforce the `Bash(...)` scoping in an agent's `tools` (see "Verified
behaviour" in `argani.md`), so the reviewer and the approver are given no `Bash` at all, and the
spec-writer only `python3 <plugin root>/scripts/*`. If a bypass is ever observed, add it to the hook
rather than widening trust.
