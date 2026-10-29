---
name: review
description: Run one review round on a job's change, one parallel reviewer per configured checklist, and summarise the verdicts. Use after the builder finishes or after rework. Slash form /argani:review <slug>.
argument-hint: "<slug>"
allowed-tools: Read, Glob, Grep, Agent, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# /argani:review

Protocol (verdict line, closing line, rounds, wait for all): `${CLAUDE_PLUGIN_ROOT}/docs/review-protocol.md`.
This skill orchestrates only: it writes no files itself (`capture_change.py` writes the change) and
never edits code. Reviewers write the review files.

## Steps

Run each command on its own, so the allowed-tools patterns match and the human is not prompted.

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py` and read `reviewers` and
   `diffCommand`. If `reviewers` contains `human` (a reserved name), **stop**. If `diffCommand` is
   empty, **stop** and name `project.json` in the argani home (`/argani:init` when it does not exist).
   Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/factory_state.py $ARGUMENTS` and take `job_dir`,
   `stage`, `review_round`, `reviewers` (the checklists this change needs: one scoped by
   `reviewerPaths` runs only when the captured change touches its paths) and `models.reviewers`.
   "Configured reviewer" below means one of these.
2. The slug folder is `job_dir` from the state. If `spec.md` is not there, **stop** and name the
   missing file. If `stage` is not `needs-build`, `needs-review` or `needs-rework`, **stop** and print
   the state's `next`: there is no round waiting for review. If `review_round` is 3 or more, **stop**:
   "two rounds maximum, escalate to a human". `N = review_round`.
3. Capture the change, unless the round already holds a review file (the change is fixed once a
   reviewer has worked on it; then `<job_dir>/review/round-<N>/change.diff` must exist already):
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture_change.py $ARGUMENTS`. It runs `diffCommand` with
   the project root as working directory and writes `<job_dir>/review/round-<N>/change.diff` (its
   JSON gives the `path`, the `bytes` and the `files`). If it exits non-zero, **stop** and show its
   output. If `bytes` is 0, **stop** and say: "diffCommand printed nothing; nothing to review. Check
   diffCommand against the builder's commit rule" (committed work and a working tree need different
   commands). Run `factory_state.py` again so `reviewers` reflects the captured change.
4. A seat is a configured reviewer without a complete `review-<name>.md` (last line
   `=== END OF REVIEW ===`) in the round folder; when the round holds only `review-human.md`, all
   seats are missing. Complete seats are not spawned again.
5. The round folder exists already (it holds `change.diff`). In **a single message**, spawn one
   Agent call per seat to run, each with `subagent_type: "argani:reviewer"`, `model` set to
   `models.reviewers.<name>` (left out when it is `inherit`), and this prompt:

   ```
   Plugin root: ${CLAUDE_PLUGIN_ROOT}
   Checklist: <name>
   Checklist file: ${CLAUDE_PLUGIN_ROOT}/checklists/<name>.md
   Slug folder: <absolute slug folder>
   Round: <N>
   Change: <slug folder>/review/round-<N>/change.diff
   Review the change and write <slug folder>/review/round-<N>/review-<name>.md.
   ```
6. Wait for all of them. Then check each expected `review-<name>.md` exists and its last line is
   `=== END OF REVIEW ===`. Rerun a missing or cut-off seat once (same prompt); if it is still
   missing, report that seat as failed.
7. Print a table: checklist, verdict (line 1 of its file; include seats kept from an earlier attempt
   in the same round), and the first Important finding (or "-"). Then the next step:
   - all `PASS`: "ready for /argani:factory or a human decision".
   - any `CHANGES` and `N == 1`: "address the findings, then run /argani:review again (round 2)".
   - any `CHANGES` and `N == 2`: "two rounds used; escalate to a human".
