---
name: review
description: Run one review round on a job's branch, one parallel reviewer per configured checklist, and summarise the verdicts. Use after the builder finishes or after rework. Slash form /sdlc:review <slug>.
argument-hint: "<slug>"
allowed-tools: Read, Glob, Grep, Agent, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git rev-parse *), Bash(git diff *)
---

# /sdlc:review

Protocol (verdict line, closing line, rounds, wait for all): `${CLAUDE_PLUGIN_ROOT}/docs/review-protocol.md`.
This skill orchestrates only: it writes no files and never edits code. Reviewers write the files.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py` and read `reviewers`, `defaultBranch`,
   `artifactRoot` and `toplevel`.
2. The slug folder is `<toplevel>/<artifactRoot>/$ARGUMENTS/`. If `spec.md` is not there, **stop**
   and name the missing file.
3. Check the change: `git -C <toplevel> rev-parse --abbrev-ref HEAD` must not equal `defaultBranch`,
   and `git -C <toplevel> diff --quiet <defaultBranch>...HEAD` must report a difference (exit 1).
   Otherwise **stop** and say there is nothing to review.
4. Pick the round number `N` from the highest existing `review/round-*` folder `H`:
   - No round folder: `N = 1`.
   - `H` is incomplete (a configured reviewer has no `review-<name>.md` in it, or a file's last line
     is not `=== END OF REVIEW ===`): `N = H`, and spawn only the missing or cut-off seats.
   - `H` contains only `review-human.md`: `N = H`, and spawn all seats.
   - Otherwise `N = H + 1`. If `N >= 3`, **stop**: "two rounds maximum, escalate to a human".
5. The round folder needs no separate step: the Write tool creates it when the first reviewer writes.
   In **a single message**, spawn one Agent call per seat to run, each with
   `subagent_type: "sdlc:reviewer"` and this prompt:

   ```
   Plugin root: ${CLAUDE_PLUGIN_ROOT}
   Checklist: <name>
   Checklist file: ${CLAUDE_PLUGIN_ROOT}/checklists/<name>.md
   Slug folder: <absolute slug folder>
   Round: <N>
   Default branch: <defaultBranch>
   Review the diff <defaultBranch>...HEAD and write <slug folder>/review/round-<N>/review-<name>.md.
   ```
6. Wait for all of them. Then check each expected `review-<name>.md` exists and its last line is
   `=== END OF REVIEW ===`. Rerun a missing or cut-off seat once (same prompt); if it is still
   missing, report that seat as failed.
7. Print a table: checklist, verdict (line 1 of its file; include seats kept from an earlier attempt
   in the same round), and the first Important finding (or "-"). Then the next step:
   - all `PASS`: "ready for /sdlc:factory or a human decision".
   - any `CHANGES` and `N == 1`: "address the findings, then run /sdlc:review again (round 2)".
   - any `CHANGES` and `N == 2`: "two rounds used; escalate to a human".
