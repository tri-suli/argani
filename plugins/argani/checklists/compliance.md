# Checklist: compliance

## Scope

Whether the work matches what was approved:

- The diff `<defaultBranch>...HEAD` matches `spec.md` and `plan.md`.
- Every acceptance criterion in the spec's mapping table has evidence in `build.md`.
- The literal output of `verifyCommand` is present in `build.md`.
- Deviations from `plan.md` are recorded in `build.md`.

## What Important means here

- The diff does something `spec.md` does not ask for, or leaves out something it asks for.
- An AC in the mapping table has no evidence in `build.md`.
- The literal `verifyCommand` output is missing, summarised instead of pasted, or shows a failure.
- The diff departs from `plan.md` without a recorded deviation.

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Code quality and style: the code checklist covers it.
- Disagreement with the spec itself: it is already approved; raise it as a note, not a finding.
- Files outside the diff.

## Output format

Write only your own file, `review/round-N/review-compliance.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
