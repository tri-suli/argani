# Checklist: format

For document repositories (documentation, knowledge bases), not code.

## Scope

The document follows the repository's template and structure (required sections, heading order,
front matter, file naming), links and cross-references resolve, and tables and code blocks render.

## What Important means here

- A required section or front matter field of the template is missing or misnamed.
- A link or cross-reference is dead or points to the wrong target.
- Structure is broken so the document cannot be read or processed (unclosed code block, broken
  table).

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Wording, tone and spelling beyond obvious typos.
- Source quality: the citation checklist covers it.
- Template choices the repository did not specify.

## Output format

Write only your own file, `review/round-N/review-format.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
