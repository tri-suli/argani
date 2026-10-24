# Review protocol

How reviews and decisions are written, counted and enforced. `hooks/guard_artifacts.py` enforces
the mechanical parts (verdict line, round limit, who writes what); the rest is instruction.

## Files

All paths are under `<artifactRoot>/<slug>/` (default `sdlc/<slug>/`).

| File | Written by | Line 1 | Last line |
|---|---|---|---|
| `review/round-N/review-<checklist>.md` | `sdlc:reviewer`, one per checklist in `reviewers` | `PASS` or `CHANGES` | `=== END OF REVIEW ===` |
| `review/round-N/review-human.md` | the orchestrator or human, from a `rework` note | `CHANGES` | `=== END OF REVIEW ===` |
| `decision.md` | `sdlc:approver` | `APPROVE` or `ESCALATE` | `=== END OF DECISION ===` |

`<checklist>` is a name from `checklists/` (`code`, `security`, `compliance`, `citation`, `format`).
`N` starts at 1.

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

- A round is **complete** only when every checklist listed in `reviewers` has a file in
  `review/round-N/` that ends with the closing line. Do not summarise, decide, or start rework
  on a partial round.
- `review-human.md` is extra: it does not count toward completeness and does not replace a seat.
- If any file in a complete round says `CHANGES`, the builder reworks and a new round `N+1` starts.
  All files are read; one `PASS` never cancels another file's `CHANGES`.
- All files `PASS` means the approver is spawned and writes `decision.md`.
- **Two rounds at most.** The hook refuses any write under `review/round-3/` or higher
  (`N >= 3`). If round 2 still has `CHANGES`, stop and escalate to a human; do not try to work
  around the refusal.
- `ESCALATE` in `decision.md` stops the job and marks it as needing a human.
- `APPROVE` still ends in a merge request, never a merge.

## One writer per file

The hook reads `agent_type` from the hook input (value `sdlc:<agent>`):

| Agent | May write | May not write |
|---|---|---|
| `sdlc:reviewer` | `<artifactRoot>/<slug>/review/round-*/review-*.md` | anything else in the repository |
| `sdlc:approver` | `<artifactRoot>/<slug>/decision.md` | anything else in the repository |
| `sdlc:spec-writer` | `<artifactRoot>/<slug>/spec.md` | anything else in the repository |
| `sdlc:builder` | everything else, including `plan.md`, `build.md` and source files | under `<artifactRoot>/<slug>/`: `intent.md`, `spec.md`, `review/**`, `decision.md`, `mr.md` |

Paths outside any git repository are not touched by this rule. The main session and other agent
types are not restricted by it. A reviewer writes only the file for its own checklist; the hook
cannot tell which checklist a reviewer was given, so that part is an instruction in the agent prompt.

## Running a round

**Manual mode.** `/sdlc:review <slug>`:
1. Read `reviewers` from `.claude/sdlc.json`.
2. In one message, spawn one `sdlc:reviewer` per checklist (parallel). Each prompt names the
   checklist file, `spec.md`, `plan.md`, the diff `<defaultBranch>...HEAD`, and its one output path.
3. Wait until every expected file exists and ends with the closing line; rerun any cut-off seat.
4. Report each verdict. The human decides whether to rework or run the approver.

**Factory mode.** `/sdlc:factory` runs the same round after the builder finishes, then:
`CHANGES` anywhere starts a new round with a fresh builder that reads the round folder;
all `PASS` spawns the approver; round 3 is refused by the hook and the job escalates.
Agents do not carry memory between steps: every spawn reads files named in its prompt.

**Human rework.** `/sdlc:factory rework <slug> <note>` writes `review/round-N+1/review-human.md`
with `CHANGES` on line 1, the note as an Important finding, and the closing line, then continues
as a normal round. It is subject to the same two-round limit.

## Accepted bypasses

The hooks are a guard against mistakes, not a sandbox. These are known and accepted:

- `git branch -f <default> ...` and `git update-ref refs/heads/<default> ...` move the default
  branch without `push`/`merge`/`pull`, and `guard_git.py` does not look for them.
- Writing a file through Bash (heredoc, `tee`, `sed -i`) bypasses `guard_artifacts.py`, which only
  sees `Write` and `Edit`.
- `xargs`, `eval` and similar indirection hide the git command from the parser. `bash|sh|zsh -c
  "<cmd>"` is analysed; other nesting is not.
- `cd ~` and `cd -` are not resolved (the hook keeps the previous directory, so it may check the
  wrong repository and allow). `--git-dir` and `--work-tree` are ignored for repository detection.
- `git push --delete` matches only when the deleted branch is the default branch.
- A broken `.claude/sdlc.json` makes the git guard use defaults and keep checking, while the
  artifact guard asks (main session) or denies (subagent) for every write in that repository,
  because `protectedPaths` cannot be checked.

Acceptable because the reviewer and approver have `Write`, but the hook limits it to their own
file, and their Bash is limited to `git diff`/`git log` (see the agent definitions). The builder has
Bash, but its prompt forbids these commands, and the protection that matters (the default branch on
the remote) is the human-owned merge request. If a bypass is ever observed, add it to the hook
rather than widening trust.
