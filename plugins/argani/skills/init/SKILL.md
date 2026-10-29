---
name: init
description: Register this directory as a project on the argani board (in the argani home, ~/.argani by default) from what it already uses (test command), asking only what cannot be detected. Never writes into the project. Use when a directory is not registered yet, or when the factory stops because verifyCommand or diffCommand is missing. Slash form /argani:init.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read
---

# /argani:init

Keys and their meaning: `${CLAUDE_PLUGIN_ROOT}/docs/config.md`. This skill writes one file,
`projects/<name>/project.json` in the argani home, through `register_project.py`. It never writes
into the project directory.

## Steps

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_config.py`. If it exits non-zero, show its output
   and stop. Keep the JSON.
2. If `homeError` is set, explain it (`ARGANI_HOME` must be an absolute path without `..`) and stop.
   If `registryError` is set, the registry in the home is inconsistent (for example two projects
   list one path): show the message, tell the human to fix the entries under `projects/` by hand,
   and stop.
3. If `registered` is set, say the directory already belongs to the project `registered`, show
   `projectFile`, and tell the human to edit that file by hand to change keys such as
   `verifyCommand` or `diffCommand` (keys in `docs/config.md`), then run
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py` to validate it. Then stop.
4. Show `proposal` as the starting point, with the project name (`project`), the directory that will
   be registered (`realPath`) and the file that will be written (`projectFile`). Then ask the human
   about each entry in `questions`, a few at a time, offering its `candidates` (none means an open
   question). Rules for the answers:
   - `project`: always confirm the name, which was taken from the folder name. When `nameTaken` is
     true a project of that name already exists: answering with the same name adds this directory
     to it, another name creates a new project. Lowercase letters, digits and dashes, starting with a
     letter or digit. It becomes the folder `projects/<name>` in the home.
   - `verifyCommand`: required; the factory refuses to run without it. A command that fails until
     the first job adds tests is fine.
   - `diffCommand`: required by the factory and the review. The project's own command that prints the
     change under review as a unified diff; argani runs it with the project root as its working
     directory and never prepares branches itself. Read the question's note to the human:
     `git diff origin/main...HEAD` shows committed work only, `git diff origin/main` shows the working
     tree but not untracked files, and the command must match the project's commit rule for the
     builder (a project that forbids agent commits needs a working-tree diff, with new files made
     visible by `git add -N`). Offer both candidates; the human adapts them.
   - `mrCommand`: optional; the candidates are the GitHub and GitLab forms. Keep `{title}` and
     `{bodyFile}` as they are, the factory fills them. Leave it out when the human wants to open
     merge requests themselves.
   Ask also whether to add checklists to `reviewers` (catalog in `docs/config.md`) and whether some
   paths must never be written by agents (`protectedPaths`). Omit keys the human leaves at their
   default.
5. If `legacyExists` is true, explain that the directory's `.claude/argani.json` is no longer read
   (since 1.0.0), that its keys (`legacyKeys`) are carried over: they are already part of the
   proposal and win over the detected values. `artifactRoot` is not carried over: a board project
   keeps its jobs in `tasks/`. Keys listed in `legacyUnknownKeys` are not argani keys any more
   (branch, worktree, merge and commit settings are the project's own business since 2.0.0) and are
   left behind. If `legacyKeys` is null, show `legacyError` and continue without them. Say the file
   may be deleted after registration, through the project's usual process; never delete it yourself.
6. Show the final config JSON and the project name, and ask for confirmation. On yes, run it with
   the config on stdin:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/register_project.py <name> <realPath> <<'EOF'
   { ...config keys... }
   EOF
   ```

   If it exits non-zero, show the message, fix the config with the human, and run it again. If it
   fails twice in a row, stop and show the message.
7. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/argani_config.py` in the directory and show `project`
   and `tasksDir`. If it exits non-zero, show the error, tell the human to fix `projectFile` by
   hand, and stop.
8. End with: nothing was written into the project. Next step: `/argani:intent <description>`.
