# argani

A Claude Code marketplace with one plugin, `sdlc`, that runs a single artifact loop for any kind of
project (applications, documentation, knowledge bases):

```
intent -> spec -> plan -> work on a branch -> review -> merge request -> operate
```

Every stage ends in a committed artifact that the next stage reads, and humans decide at the gates.
The loop has two modes: **manual** (you call the skills one by one) and **factory** (an orchestrator
runs spec, build, review and decision with subagents, and stops at a merge request). Agents never
merge their own work. See [`plugins/sdlc/docs/sdlc.md`](plugins/sdlc/docs/sdlc.md) for the full
reference and [`INTENT.md`](INTENT.md) for the project intent.

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
  "enabledPlugins": { "sdlc@argani": true }
}
```

Per-repository options live in `.claude/sdlc.json`; see
[`plugins/sdlc/docs/config.md`](plugins/sdlc/docs/config.md).

## Local development

```bash
claude plugin validate . --strict
claude plugin marketplace add ./
claude plugin install sdlc@argani
# inside a session:
/reload-plugins
```

`bash scripts/check.sh` runs both validations and the test suite.

## Layout

```
.claude-plugin/marketplace.json   marketplace manifest
plugins/sdlc/                     the plugin
  .claude-plugin/plugin.json
  docs/                           loop reference, configuration schema, review protocol
  templates/                      intent, spec, plan, build
  checklists/                     code, security, compliance, citation, format
  hooks/                          default-branch guard, artifact guard
  scripts/                        config loader and artifact checker
  agents/                         spec-writer, builder, reviewer, approver
  skills/                         intent, spec, plan, review
  tests/                          pytest suites
scripts/check.sh                  validate and test
bootstrap/                        global configuration (planned)
```

## Status

| Component | Status |
|---|---|
| Skills `/sdlc:intent`, `/sdlc:spec`, `/sdlc:plan` | available |
| Hooks (default-branch guard, verdict and path guards) | available |
| Agents (spec-writer, builder, reviewer, approver) | available |
| Review protocol and checklists | available |
| Skill `/sdlc:review` | available |
| Factory orchestrator `/sdlc:factory` | planned |
| Evals | planned |
| Bootstrap | planned |

## License

[MIT](LICENSE)
