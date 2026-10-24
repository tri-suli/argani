# Checklist: security

## Scope

Security problems introduced or exposed by the diff: injection (shell, SQL, path, template),
missing authentication or authorization, unsafe deserialization, secrets or credentials in the
diff, weak cryptography, unvalidated input crossing a trust boundary, and new dependencies with
known problems.

## What Important means here

- Attacker-controlled input reaches a sink without validation or escaping.
- A secret, token, key or personal data is committed or logged.
- An access check is missing or can be bypassed.

Anything else worth saying that does not meet this bar is a Nit.

## Cap the nits

Report at most 5 nits. If there are more, keep the five that matter most and state how many were
dropped. Never return `CHANGES` for nits alone.

## Do not report

- Theoretical issues with no reachable path in this code.
- Hardening wishes unrelated to the diff.
- General correctness and style: other checklists cover them.

## Output format

Write only your own file, `review/round-N/review-security.md`, and nothing else. Follow
`docs/review-protocol.md`:

- Line 1 is exactly `PASS` or `CHANGES`, optionally followed by a space and a short reason. No
  heading or blank line before it. `PASS` means no Important finding.
- Then one bullet per finding: `- [Important|Nit] file:line - What: ... Why: ... Fix: ...`
- The last line is exactly `=== END OF REVIEW ===`. Without it the file counts as cut off and the
  seat is rerun.
