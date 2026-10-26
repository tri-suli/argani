# argani evals

Behavioural checks that need a real model run. Deterministic logic (scripts, hooks) is covered by
pytest in `../tests`, not here. The eval fixtures are validated by `../tests/test_eval_fixtures.py`
so they cannot drift from `artifact_check.py`.

## Run

```bash
claude plugin eval plugins/argani --runs 1 --max-cost-usd 3 --trust-plugin --no-publish \
  --ablation none --scaffold --allow-tools Write Bash Edit Read Agent
```

- `--scaffold` is required: two cases build a fixture repository with `scaffold.sh` (needs git >= 2.28 for `git init -b`).
- `--trust-plugin` is required headless; `--ablation none` skips the no-plugin baseline arm.
- `--case <glob>` runs a single case, for example `--case 'intent-*'`.
- Cost: about $0.30 for both cases at `--runs 1` (about $0.10 to $0.20 per case).
- Do not run while `argani@argani` is installed and enabled; the session would see duplicate skills
  and agents. Results are written to `evals/results/` (gitignored).

## Cases

| Case | Guards |
|---|---|
| `intent-produces-artifact` | `/argani:intent` writes `argani/demo-login/intent.md` as a draft with the template title and every AC in the `- AC-n: ... — verify: ...` shape; an LLM judge checks verification quality, sections and language consistency. |
| `spec-refuses-unapproved-intent` | `/argani:spec` on a draft intent writes no `spec.md`, says the intent is not approved and names `/argani:intent approve demo-login`. |

## Not covered by evals

The eval sandbox masks `git` (`/usr/bin/git` is the null device and every call fails with
`Permission denied`), so anything that needs a repository cannot be evaluated: `/argani:review`, the
reviewer's diff and the factory. Those contracts are covered by the hook and script tests (pytest) and
by this manual headless smoke:

1. Make a scratch repo on the job branch (`feature/<slug>` by default) with `main` behind it and a
   commit that contains a small, obvious bug.
2. Add `.claude/settings.json` with `{"enabledPlugins": {"argani@argani": true}}` (the marketplace
   must be registered) and `.claude/argani.json` with `{"reviewers": ["code"]}`.
3. Add `argani/<slug>/` with an approved `intent.md` and `spec.md`, a `plan.md`, and a `build.md`
   ending in `=== END OF BUILD ===`.
4. Run, from the repo root:

   ```bash
   env -u CLAUDECODE claude -p "/argani:review <slug>" --output-format json \
     --permission-mode acceptEdits --allowedTools "Agent,Bash,Read,Write,Glob,Grep" --max-turns 15
   ```

5. Check: `argani/<slug>/review/round-1/review-code.md` exists; line 1 is `PASS` or `CHANGES` (here
   `CHANGES`); the last line is `=== END OF REVIEW ===`; a finding names the buggy file with a
   `file:line`; the reviewer did not report being unable to read the diff.
