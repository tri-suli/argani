# The sdlc loop

Reference for the `sdlc` plugin. It is neutral to project type (applications, documentation,
knowledge bases) and to organization.

## Thesis

Writing the work is no longer the bottleneck. The bottleneck moved to the stages around it:
deciding what is wanted, designing, reviewing, testing, releasing. Those stages run at human
speed and mostly inside conversations, which leave no audit trail. The plugin turns each stage
into a committed artifact, so that who asked for what, what an agent produced, and who approved
it are all readable from the repository.

The loop is one and the same in every mode:

```
intent -> spec -> plan -> work on a branch -> review -> merge request -> operate -> new intent
```

Each stage ends with an artifact; the next stage reads only that artifact.

## Stages

| Stage | Artifact | Produced by | Human gate |
|---|---|---|---|
| Intent | `intent.md` | `/sdlc:intent` (interview with the human) | Human approves the intent |
| Spec | `spec.md` | `/sdlc:spec` or the spec-writer agent | Human reviews and approves the spec |
| Plan | `plan.md` | `/sdlc:plan` or the builder agent | Manual mode: human approves before any change. Factory mode: reviewed in the MR |
| Work | code or documents on branch `sdlc/<slug>`, `build.md` | Human or builder agent | none |
| Review | `review/round-N/review-<checklist>.md` | Reviewer agents | none |
| Decision | `decision.md` | Approver agent | Its output is a merge request, never a merge |
| Operate | follow-up intents | Human, from what production shows | Human opens the next intent |

Operate is recorded as a stage but not yet automated.

## Artifact location

Per job, in `<artifactRoot>/<slug>/` (default `sdlc/<slug>/`, see `config.md`):

```
intent.md     Status: draft | approved by <name> on <YYYY-MM-DD>; acceptance criteria in a fixed shape
spec.md       same Status forms; maps each AC to how it is verified; flags concerns
plan.md       files that change, order, risks, proof
build.md      work done, literal verification output, deviations; ends with === END OF BUILD ===
review/round-N/review-<checklist>.md   line 1 is PASS or CHANGES; ends with === END OF REVIEW ===
decision.md   line 1 is APPROVE or ESCALATE; ends with === END OF DECISION ===
mr.md         merge request URL and branch, written once the MR exists
```

Acceptance criteria use one shape, checked by `scripts/artifact_check.py`:

```
- AC-1: <claim> — verify: <command | test | named manual step>
```

Artifact prose follows the language of the repository's `CLAUDE.md` or of the user. File names,
Status lines, `AC-n`, `verify:` and verdict words stay in English.

## Always-on rules

1. Skills advise, hooks enforce. Anything that must always hold is a hook reading the repo config.
2. Nobody approves their own work. The approver's output is a merge request for a human; agents
   never merge or push to the default branch.
3. Context comes from files, not conversation. Every agent is told which paths to read.
4. One writer per file. Each agent writes only its own artifact.
5. Acceptance criteria must be verifiable. Intent without a command, test, or named manual step
   per criterion cannot be approved.
6. The verdict is the first line of a review (`PASS` or `CHANGES`) or decision (`APPROVE` or `ESCALATE`).
7. At most two review rounds, then escalate to a human.
8. A correction made twice becomes a rule in the repo's `CLAUDE.md` or a hook.

## Two modes

**Manual.** A person calls the skills one at a time and performs each gate in place:
`/sdlc:intent`, approve, `/sdlc:spec`, approve, `/sdlc:plan`, approve, then does or directs the work.

**Factory.** `/sdlc:factory` turns the session into an orchestrator that runs spec, build, review
and decision with fresh subagents, each reading and writing files. It stops at only three
places: the intent (human approves), the spec (human approves), and the merge request (human
reviews and merges). `plan.md` is written by the builder before it changes any code and is
reviewed together with the diff in the merge request. Factory mode is expensive (several agents
per job, up to two rounds), so use it only for jobs with clear acceptance criteria.

## Reviewers

There is one generic reviewer agent. What it checks comes from a checklist in the catalog
(`code`, `security`, `compliance`, `citation`, `format`). The repository chooses the active
checklists through `reviewers` in `.claude/sdlc.json`.

## Adoption order

1. Intent, spec and plan skills; usable immediately, by hand.
2. Review protocol and enforcing hooks.
3. Generic agents and the checklist catalog.
4. Factory orchestrator ending in a merge request.
5. Eval suite, then bootstrap of global configuration.

## Verified behaviour

_Filled from the spike: facts observed by running the plugin, not read from documentation._
