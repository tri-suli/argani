# Checklist: ux

## Scope

How a person moves through the user-facing behaviour changed in the diff `<defaultBranch>...HEAD`,
judged from the code and from the flows described in `spec.md`: every state a screen or command
can reach (loading, empty, error, success, partial data), feedback after an action, form
validation and its messages, destructive actions and how they are confirmed or undone, keyboard
and screen-reader access (semantic elements, labels, focus order, focus after navigation or
dialogs), and the wording of labels, messages and errors shown to users.

The reviewer cannot run the interface. Every finding must point to code in the diff that shows
the problem.

## What Important means here

- A flow described in `spec.md` cannot be completed, or the code takes the user somewhere else.
- A state the user can reach (error, empty, loading) has no handling or leaves them stuck.
- A destructive or irreversible action runs without confirmation or a way back.
- An interactive element cannot be reached or operated by keyboard, or has no accessible name.
- An error is shown to the user as a raw exception, code or stack trace, or not shown at all.

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Visual styling, spacing, colour and layout: the `ui-design` checklist covers them.
- Taste: wording or flow preferences that the spec or the repo's conventions do not require.
- Screens and flows the diff does not touch.
- Correctness of logic behind the interface: the `code` checklist covers it.

## Output format

Write only your own file, `review/round-N/review-ux.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
