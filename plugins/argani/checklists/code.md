# Checklist: code

## Scope

Correctness of the change in `change.diff`: logic errors, unhandled edge
cases, regressions in existing behaviour, missing or weak tests for new behaviour, broken
error handling at real boundaries, and names in the diff (files, modules, functions, identifiers,
test cases and fixtures) that a human cannot understand or that break names already agreed.

## What Important means here

- The code is wrong in a way a user or caller can hit (wrong result, crash, data loss).
- Existing behaviour regresses, or new behaviour has no test that would fail without it.
- An error path swallows a failure that the caller must know about.
- A name in the diff is an opaque internal label (`a1`, `case3`, `round2`, `tmp2`) or records when
  or by whom something was made, instead of saying what it is or does.
- A name differs from the one `spec.md`, `plan.md` or the existing code already uses for the same
  thing, or the diff mixes two naming patterns for the same kind of thing.

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Style, naming and formatting preferences that a linter or the repo's conventions do not require
  (a name that is descriptive and consistent but not the one you would pick is not a finding).
- Hypothetical problems with no path to trigger them.
- Code the diff does not touch.
- Security and spec conformance: other checklists cover them.

## Output format

Write only your own file, `review/round-N/review-code.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
