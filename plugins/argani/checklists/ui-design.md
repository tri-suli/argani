# Checklist: ui-design

## Scope

Visual consistency of the interface changed in `change.diff`, judged from
markup, styles and components: use of the repository's design system (tokens, theme variables,
shared components) instead of hard-coded colours, sizes, spacing or fonts; reuse of existing
components instead of near-copies; layout at the breakpoints the repository supports; text
contrast; light and dark themes when the repository has both; and conformance with any design
reference that `spec.md` names.

The reviewer cannot render the interface. Every finding must point to code in the diff that shows
the problem.

## What Important means here

- A value the design system defines as a token or theme variable is hard-coded, or a shared
  component is duplicated with a local variant.
- A layout uses fixed widths or positions that break a supported breakpoint (overflow, clipped
  or overlapping content).
- A text and background colour pair falls below WCAG AA contrast (4.5:1, or 3:1 for large text).
- The change ignores a theme the repository supports (for example, colours fixed for light mode
  only).
- The result contradicts a design reference that `spec.md` names.

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Personal taste in colour, typography or layout that the design system and spec do not require.
- Flows, states, wording and keyboard access: the `ux` checklist covers them.
- Styles the diff does not touch.
- A missing design system: if the repository has none, report only what contradicts `spec.md`.

## Output format

Write only your own file, `review/round-N/review-ui-design.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
