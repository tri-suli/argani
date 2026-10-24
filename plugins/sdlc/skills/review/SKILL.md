---
name: review
description: Run one review round on a job's branch, one parallel reviewer per configured checklist, and summarise the verdicts. Use after the builder finishes or after rework. Slash form /sdlc:review <slug>.
argument-hint: "<slug>"
allowed-tools: Read, Glob, Grep, Agent, Write, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git *)
---

# /sdlc:review

Protocol (verdict line, closing line, rounds, wait for all): `../../docs/review-protocol.md`.
This skill orchestrates; it never writes inside the round folder itself and never edits code.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdlc_config.py` and read `reviewers`, `defaultBranch`,
   `artifactRoot` and `toplevel`.
2. The slug folder is `<toplevel>/<artifactRoot>/$ARGUMENTS/`. If `spec.md` is not there, **stop**
   and name the missing file.
3. Round `N` = 1 + the highest existing `review/round-*` number (1 if none). If `N >= 3`, **stop**:
   "two rounds maximum, escalate to a human".
4. The round folder `<slug folder>/review/round-N/` needs no separate step: the Write tool creates it
   when the first reviewer writes its file.
5. In **a single message**, spawn one Agent call per checklist in `reviewers`, each with
   `subagent_type: "sdlc:reviewer"` and this prompt:

   ```
   Checklist: <name>
   Checklist file: ${CLAUDE_PLUGIN_ROOT}/checklists/<name>.md
   Slug folder: <absolute slug folder>
   Round: <N>
   Default branch: <defaultBranch>
   Review the diff <defaultBranch>...HEAD and write <slug folder>/review/round-<N>/review-<name>.md.
   ```

   Substitute the real `${CLAUDE_PLUGIN_ROOT}` value in the path.
6. Wait for all of them. Then check each expected `review-<name>.md` exists and its last line is
   `=== END OF REVIEW ===`. Rerun a missing or cut-off seat once (same prompt); if it is still
   missing, report that seat as failed.
7. Print a table: checklist, verdict (line 1 of its file), and the first Important finding
   (or "-"). Then the next step:
   - all `PASS`: "ready for /sdlc:factory or a human decision".
   - any `CHANGES`: "address the findings, then run /sdlc:review again (round N+1)".
