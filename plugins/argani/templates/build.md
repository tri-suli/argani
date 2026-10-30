# Build: {{title}}

Spec: {{slug}}
Date: {{YYYY-MM-DD}}

<!-- Written by the builder when work is finished. On rework, append a section
     `## Rework after round {{K}}` for each round folder whose findings were addressed, instead of
     rewriting earlier content. -->

## What was done

<!-- Summary of the changes actually made, grouped by area. The last line is the commit statement
     (for example `Commit: via <skill> per <protocol file>`, `Commit: none, protocol forbids agent commits`). -->

- {{change}}

## Verification output

<!-- Paste the literal output of the verify command. Do not paraphrase or abbreviate. -->

```
{{output of verifyCommand}}
```

## Pending human verification

<!-- One item per AC whose verification is `manual: <step>`: the AC, the step, and what this build
     prepared for it (a command to run, a file to inspect). Do not claim these as verified.
     Write "None" if there are none. -->

- {{AC-n: step, and what was prepared}}

## Deviations from plan

<!-- Where the work differs from plan.md and why. Write "None" if there are none. -->

- {{deviation}}

=== END OF BUILD ===
