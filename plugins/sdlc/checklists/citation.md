# Checklist: citation

For document repositories (documentation, knowledge bases), not code.

## Scope

Every claim that needs a source has one, each source exists and can be traced (URL, file,
section), quotes are accurate, and the source supports the claim made.

## What Important means here

- A factual claim, number or quote has no source.
- A cited source does not exist, cannot be reached, or does not say what the text claims.
- A quote is altered or taken out of context so that its meaning changes.

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Citation style preferences when the source is traceable.
- Claims that are the author's own reasoning and are marked as such.
- Structure and formatting: the format checklist covers it.

## Output format

Write only your own file, `review/round-N/review-citation.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
