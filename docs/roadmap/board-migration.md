# Roadmap: argani as a local project board

Status: plan, agreed on 2026-10-28. Nothing here is implemented yet.

## Why

The pilot in a real repository showed that the per-repository model costs too much: every project
needs `.claude/argani.json`, a job folder under `artifactRoot`, record commits that pass the
repository's commitlint, and a `commitSkill`. argani kept growing options to fit each repository.

The new model turns this around:

- argani is installed at **user scope** and acts as a **local board** (like Trello or ClickUp) for
  every project, with markdown files as the material, following the `factory/` layout of the
  zazencodes Software Factory (`backlog`, `jobs/<id>/...`).
- Board data lives in **`~/.argani`** (override with `ARGANI_HOME`), apart from the plugin code,
  and can be a private git repository. The installed plugin is a cached copy per version, so it
  never stores data.
- Project repositories are left alone: no `.claude/argani.json`, no job folder, no record commits.
  Only code reaches a project, through a branch and a merge request.
- Who merges is a per-project choice (`mergePolicy`). With `human` (the default) a human merges the
  merge request, as today. With `agent` the user lets agents and subagents commit, push, pull, open
  the merge request and merge it themselves; the factory then merges after `APPROVE`. Branch
  protection on the remote still applies in both cases.
- The audit trail moves to the git history of `~/.argani`. The project's merge request carries
  the acceptance criteria and a reference to the task folder.
- The per-repository mode keeps working during the migration and is removed in **1.0.0**. An
  import skill moves existing jobs to the board.
- A **virtual office** to monitor agents and subagents comes later, as a separate application
  that only reads board data.

## Architecture

Architecture diagram: [`diagrams/architecture.mmd`](diagrams/architecture.mmd)

## Task flow and board columns

Task flow diagram: [`diagrams/task-flow.mmd`](diagrams/task-flow.mmd)

Columns are derived from the `stage` that `factory_state.py` already computes; the board stores no
separate status:

| `factory_state.py` stage                                        | Column       |
|-----------------------------------------------------------------|--------------|
| `needs-intent-approval`                                         | Backlog      |
| `needs-spec`, `needs-spec-approval`                             | Design       |
| `needs-build`, `needs-rework`, `needs-review`, `needs-decision` | In progress  |
| `needs-mr`                                                      | Ready for MR |
| `done` (`mr.md` exists)                                         | In review    |
| `done` and the job branch is merged into its base               | Done         |
| `escalate`                                                      | Needs human  |

## Scopes

One scope is one pull request that can be reviewed and tested on its own. A scope starts only after
every scope in its "Depends on" column is finished.

### Epic A: board foundation

| ID | Depends on | Scope                                                                                                                                                                                                                                             | Main files                                                            | Done when                                                                                                                            |
|----|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| A1 | -          | Hub location: `ARGANI_HOME` (default `~/.argani`), folder layout, idempotent first creation                                                                                                                                                       | `scripts/argani_home.py` (new), tests                                 | tests: the env var is honoured, folders are created once, relative paths and `..` are refused                                        |
| A2 | A1         | Project registry: `projects/<project>/project.md` (front matter: remotes, paths, `verifyCommand`, `baseBranch`, `branchPattern`, `reviewers`, `mrCommand`, ...); the current directory resolves to a project by remote URL, then by toplevel path | `scripts/project_registry.py` (new), reuses `argani_config.py` checks | tests: a worktree and a second clone with the same remote resolve to the same project; an unregistered project gives a clear message |
| A3 | A2         | `/argani:init` registers the project in the hub instead of writing `.claude/argani.json`; reuses the detection in `init_config.py`                                                                                                                | `skills/init/SKILL.md`, `scripts/init_config.py`                      | init in a scratch repository writes `project.md`; the repository stays unchanged (`git status` clean)                                |
| A4 | A2         | Board model: the column comes from the stage (table above); `board.md` per project and an all-projects summary are generated from the task folders                                                                                                | `scripts/board.py` (new), uses `factory_state.py`                     | one test per column; `board.md` is deterministic (stable order)                                                                      |
| A5 | A4         | `/argani:board [--all]`: shows the current project's board or every project; read only                                                                                                                                                            | `skills/board/SKILL.md` (new)                                         | in a registered repository it prints the columns; in an unregistered one it suggests `/argani:init`                                  |

### Epic B: the argani loop runs on the board

| ID | Depends on | Scope                                                                                                                                                                                                                                                      | Main files                                                                    | Done when                                                                                                     |
|----|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| B1 | A2         | Config source: `argani_config.py` loads the project's `project.md` from the hub; `.claude/argani.json` stays as a fallback until C2                                                                                                                        | `scripts/argani_config.py`                                                    | tests: the hub wins over the repository file; with neither, the defaults apply                                |
| B2 | B1         | `intent`, `spec` and `plan` write to `~/.argani/projects/<project>/tasks/<slug>/`; slugs are unique per project                                                                                                                                            | `skills/{intent,spec,plan}/SKILL.md`, `scripts/artifact_check.py`             | the manual intent, spec, plan flow in a scratch repository leaves that repository untouched                   |
| B3 | B1         | Factory and review: `job_dir` is in the hub; the builder still works in the project checkout; record commits go to the hub's git (free message, no project commitlint); reviewers get the project path for the diff                                        | `scripts/factory_state.py`, `skills/{factory,review}/SKILL.md`, `agents/*.md` | a sample factory run reaches `needs-mr`; the project repository holds only the builder's code commits         |
| B4 | B2, B3     | `guard_artifacts.py` enforces its rules on hub paths: one writer per file, verdict on line 1, two rounds at most; `protectedPaths` stay relative to the project repository                                                                                 | `hooks/guard_artifacts.py`, tests                                             | the existing deny and allow tests pass with hub paths                                                         |
| B5 | B4         | Merge request: `mr.md` lives in the hub; the project's merge request description lists the acceptance criteria and refers to the task folder                                                                                                               | `skills/factory/SKILL.md`                                                     | a sample merge request lists the criteria; its diff has no argani files                                       |
| B6 | B5         | Merge policy: `mergePolicy` (`human` or `agent`) in `project.md` (default `human`). `guard_git.py` gates merging into a protected branch only under `human`; under `agent` the factory merges the merge request after `APPROVE` and the task moves to Done | `hooks/guard_git.py`, `skills/factory/SKILL.md`, tests                        | tests: `human` keeps today's ask/deny; `agent` lets a subagent merge; a sample run under `agent` ends in Done |

### Epic C: migration and the 1.0.0 release

| ID | Depends on | Scope                                                                                                                                                                             | Main files                                               | Done when                                                                     |
|----|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|-------------------------------------------------------------------------------|
| C1 | B5         | `/argani:import`: copies `<artifactRoot>/<slug>/` from a repository into the hub, verifies the copy, then offers to remove the folder from the repository through a normal branch | `skills/import/SKILL.md`, `scripts/import_jobs.py` (new) | existing jobs from the pilot repository show on the board with the same stage |
| C2 | C1         | Remove the per-repository mode: `.claude/argani.json`, `artifactRoot`, `recordCommitMessage`, `commitSkill` for records; update the docs; release 1.0.0; tell the pilot session   | `scripts/argani_config.py`, `docs/*`, `CHANGELOG.md`     | `scripts/check.sh` passes; nothing in the plugin refers to `argani.json`      |

### Epic D: agent monitoring and the virtual office

| ID | Depends on | Scope                                                                                                                                                                                                            | Main files                                         | Done when                                         |
|----|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------|---------------------------------------------------|
| D1 | A4         | Event log: a hook records each argani subagent's start and end (agent, model, project, slug, time, result) in `~/.argani/events/<date>.jsonl`; a small spike first confirms which hook events carry these fields | `hooks/record_events.py` (new), `hooks/hooks.json` | one factory run produces complete event lines     |
| D2 | D1         | Read snapshot for user interfaces: `board.json` (projects, tasks, columns, active agents) generated from the task folders and the event log                                                                      | `scripts/board.py`                                 | the schema is documented; snapshot tests          |
| D3 | D2         | Virtual office: an application in a separate repository that only reads `board.json` and `events/`; its technology and shape are decided when this scope starts                                                  | new repository                                     | lives outside this repository; planned on its own |

Items from the old queue that still matter after the migration: worktree mode
(`worktreeCommand`) and a sequence number `{n}` in branch names, both built on top of B3. Most of
the planned `/argani:init` detection work is no longer needed.
