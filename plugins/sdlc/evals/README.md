# sdlc evals

Behavioural checks that need a real model run. Deterministic logic (scripts, hooks) is covered by
pytest in `../tests`, not here. The eval fixtures are validated by `../tests/test_eval_fixtures.py`
so they cannot drift from `artifact_check.py`.

## Run

```bash
claude plugin eval plugins/sdlc --runs 1 --max-cost-usd 3 --trust-plugin --no-publish \
  --ablation none --scaffold --allow-tools Write Bash Edit Read Agent
```

- `--scaffold` is required: two cases build a fixture repository with `scaffold.sh` (needs git >= 2.28 for `git init -b`).
- `--trust-plugin` is required headless; `--ablation none` skips the no-plugin baseline arm.
- `--case <glob>` runs a single case, for example `--case 'review-*'`.
- Cost: about $0.50 for all three cases at `--runs 1` (about $0.10 to $0.20 per case).
- Do not run while another `sdlc` plugin is installed from the `argani` marketplace; the session
  would see duplicate skills and agents. Results are written to `evals/results/` (gitignored).

## Cases

| Case | Guards |
|---|---|
| `intent-produces-artifact` | `/sdlc:intent` writes `sdlc/demo-login/intent.md` as a draft with the template title and every AC in the `- AC-n: ... — verify: ...` shape; an LLM judge checks verification quality, sections and language consistency. |
| `spec-refuses-unapproved-intent` | `/sdlc:spec` on a draft intent writes no `spec.md`, says the intent is not approved and names `/sdlc:intent approve demo-login`. |
| `review-verdict-first-line` | `/sdlc:review` produces `review/round-1/review-code.md` whose first line is `PASS` or `CHANGES`, which ends with `=== END OF REVIEW ===`, and which reports the planted bug in `calc.py` as `CHANGES`. |

## Known limitation: git is unavailable inside the eval sandbox

In a kept eval sandbox (`--keep-temp`) `/usr/bin/git` is a character device (`crw-rw-rw- 1,3`, the
null device), so every `git` call fails with `Permission denied`, and the shell cannot write its
cwd file (`Read-only file system`). This is the runner's sandbox, not a tool grant: `Bash` was
granted with `--allow-tools` and ran fine, so no extra flag fixes it. Consequences for
`review-verdict-first-line`: `sdlc_config.py` reports `toplevel: null`, and `/sdlc:review` either
stops at step 2 without spawning a reviewer (file missing, all file graders fail) or a reviewer
reviews without the diff. The rubric fails the latter ("could not read the git diff"). The case is
kept because it is the only one that exercises the review verdict contract; expect it to be
unreliable until the runner exposes git.
