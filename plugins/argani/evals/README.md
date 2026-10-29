# argani evals

Behavioural checks that need a real model run. Deterministic logic (scripts, hooks) is covered by
pytest in `../tests`, not here. The eval fixtures are validated by `../tests/test_eval_fixtures.py`
so they cannot drift from `artifact_check.py`.

## Run

```bash
claude plugin eval plugins/argani --runs 1 --max-cost-usd 3 --trust-plugin --no-publish \
  --ablation none --scaffold --allow-tools Write Bash Edit Read Agent
```

- `--scaffold` is required: the case builds a fixture project with `scaffold.sh` (needs `python3`; no git). The script registers the current directory as the project `demo` in the argani home, which is `~/.argani` of the eval sandbox (the plugin's default, so the model run finds it without any variable; `$ARGANI_HOME` is honoured when set). It writes the home's path to `<cwd>/.argani-home-path` and links `<cwd>/.argani-home` to it, the fixed path the graders read. The project is found through the registered path of the working directory (`project_registry.resolve` matches the real path of the directory and of its ancestors against `paths`).
- `--trust-plugin` is required headless; `--ablation none` skips the no-plugin baseline arm.
- `--case <glob>` runs a single case, for example `--case 'spec-*'`.
- Cost: about $0.10 to $0.20 for the case at `--runs 1`.
- Do not run while `argani@argani` is installed and enabled; the session would see duplicate skills
  and agents. Results are written to `evals/results/` (gitignored).

## Cases

| Case | Guards |
|---|---|
| `spec-refuses-unapproved-intent` | `/argani:spec` on a draft intent writes no `spec.md`, says the intent is not approved and names `/argani:intent approve demo-login`. |

## Not covered by evals

Writing artifacts needs a writable argani home outside the working directory, which the sandbox does not offer (its `HOME` is read-only outside the cwd), so `/argani:intent` has no eval case. It is covered by the headless smoke in a scratch directory: `claude -p --plugin-dir plugins/argani "/argani:intent approve <slug>"` in a registered directory with `ARGANI_HOME` set (as done for 0.12.0).

The eval sandbox masks `git` (`/usr/bin/git` is the null device and every call fails with
`Permission denied`). argani needs none since 2.0.0, but a `diffCommand` that uses git cannot run
there, so the review and the factory still have no eval case. Those contracts are covered by the hook
and script tests (pytest) and by this manual headless smoke:

1. Make a scratch project directory (a git repository, if your `diffCommand` uses git) with a
   change that contains a small, obvious bug, and a `diffCommand` that prints it, for example
   `git diff main...HEAD`.
2. Add `.claude/settings.json` with `{"enabledPlugins": {"argani@argani": true}}` (the marketplace
   must be registered), export `ARGANI_HOME=<a scratch folder>` and register the directory with
   `echo '{"reviewers": ["code"], "diffCommand": "git diff main...HEAD"}' | python3 <plugin root>/scripts/register_project.py demo .`.
3. Add `$ARGANI_HOME/projects/demo/tasks/<slug>/` with an approved `intent.md` and `spec.md`, a
   `plan.md`, and a `build.md` ending in `=== END OF BUILD ===`.
4. Run, from the project directory:

   ```bash
   env -u CLAUDECODE claude -p "/argani:review <slug>" --output-format json \
     --permission-mode acceptEdits --allowedTools "Agent,Bash,Read,Write,Glob,Grep" --max-turns 15
   ```

5. Check: `$ARGANI_HOME/projects/demo/tasks/<slug>/review/round-1/change.diff` holds the change;
   `review/round-1/review-code.md` exists; line 1 is `PASS` or `CHANGES` (here `CHANGES`); the last
   line is `=== END OF REVIEW ===`; a finding names the buggy file with a `file:line`; the reviewer
   did not report being unable to read the change.
