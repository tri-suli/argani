# argani

A Claude Code marketplace with one plugin, `argani`, that runs a single artifact loop for any kind of
project (applications, documentation, knowledge bases):

```
intent -> spec -> plan -> work on a branch -> review -> merge request -> operate
```

Every stage ends in a committed artifact that the next stage reads, and humans decide at the gates.
The loop has two modes: **manual** (you call the skills one by one) and **factory** (an orchestrator
runs spec, build, review and decision with subagents, and stops at a merge request). Agents never
merge their own work. See [`plugins/argani/docs/argani.md`](plugins/argani/docs/argani.md) for the full
reference.

## Install

Register the marketplace once, in your user settings:

```json
{
  "extraKnownMarketplaces": {
    "argani": {
      "source": { "source": "github", "repo": "tri-suli/argani" }
    }
  }
}
```

Enable the plugin per repository, in `.claude/settings.json`:

```json
{
  "enabledPlugins": { "argani@argani": true }
}
```

Per-repository options live in `.claude/argani.json`; `/argani:init` creates it from what the
repository already uses. See [`plugins/argani/docs/config.md`](plugins/argani/docs/config.md).

## Local development

```bash
claude plugin validate . --strict
claude plugin marketplace add ./
claude plugin install argani@argani
# inside a session:
/reload-plugins
```

`bash scripts/check.sh` runs both validations and the test suite.

## Releasing

Claude Code caches an installed plugin by version, so a change only reaches installed copies with a
new version. Any change under `plugins/argani/` since the last `v*` tag needs a higher `version` in
`plugins/argani/.claude-plugin/plugin.json` (SemVer) and a `## [x.y.z]` section in `CHANGELOG.md`;
`scripts/check.sh` fails otherwise. After merging, tag the release (`git tag vX.Y.Z`) on `main`.
Installed copies then update with `claude plugin marketplace update argani` and
`claude plugin update argani@argani`, then a restart of the session.

## Factory mode

Prerequisites: an approved `intent.md` (the factory writes the spec and stops for your approval), and
`verifyCommand` plus `reviewers` in `.claude/argani.json`.

```
/argani:factory <slug>                 # advances until the next human gate, then stops
/argani:factory rework <slug> <note>   # add a human CHANGES note after a clean round 1
```

It stops at the spec (approve it, then run it again) and at the merge request. With `mrCommand`
configured it pushes the job branch and opens the MR; without it, it only prints the push and MR
instructions. Cost: one spec-writer, one builder per round, one reviewer per checklist per round,
one approver; use it for jobs with clear acceptance criteria.

## Layout

```
.claude-plugin/marketplace.json   marketplace manifest
plugins/argani/                   the plugin
  .claude-plugin/plugin.json
  docs/                           loop reference, configuration schema, review protocol
  templates/                      intent, spec, plan, build
  checklists/                     code, security, compliance, ux, ui-design, citation, format
  hooks/                          default-branch guard, artifact guard
  scripts/                        config loader and proposer, artifact checker, factory state reporter
  agents/                         spec-writer, builder, reviewer, approver
  skills/                         init, intent, spec, plan, review, factory
  evals/                          eval cases run with `claude plugin eval`
  tests/                          pytest suites
scripts/check.sh                  validate and test
```

## Status

| Component | Status |
|---|---|
| Skill `/argani:init` (creates `.claude/argani.json`) | available |
| Skills `/argani:intent`, `/argani:spec`, `/argani:plan` | available |
| Hooks (default-branch guard, verdict and path guards) | available |
| Agents (spec-writer, builder, reviewer, approver) | available |
| Review protocol and checklists | available |
| Skill `/argani:review` | available |
| Factory orchestrator `/argani:factory` | available |
| Evals (`plugins/argani/evals`, two cases) | available |

## License

[MIT](LICENSE)
